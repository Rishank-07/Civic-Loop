"""
Civic Knowledge Ingestion & Retrieval Service (Feature 3)
Grounds AI agent recommendations in official BBMP/BWSSB/Sakala/BESCOM documentation.
Embeddings generated using open-weight models (BGE-M3 / Qwen3-Embedding).
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.knowledge import KnowledgeChunk
from backend.app.ai.llm import llm_client
from backend.app.domain.case_linking import cosine_similarity

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge"


import asyncio
import re

def _generate_fallback_embedding(text: str, dim: int = 768) -> List[float]:
    """Deterministic word-hash bag-of-words normalized pseudo-embedding."""
    import hashlib
    import math

    vec = [0.0] * dim
    words = re.findall(r'\w+', text.lower())
    if not words:
        return [0.0] * dim

    for w in words:
        h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


async def get_text_embedding(text: str) -> List[float]:
    """
    Attempts to get embeddings from open-weight model runner with fast timeout.
    Falls back to deterministic bag-of-words pseudo-embedding on offline/test environment.
    """
    try:
        return await asyncio.wait_for(
            llm_client.embed(text=text, purpose="knowledge_embedding"),
            timeout=0.15,
        )
    except Exception as exc:
        logger.debug(f"LLM embed endpoint unreachable ({exc}); using fallback vector.")
        return _generate_fallback_embedding(text)


async def ingest_knowledge_seed(db: Session, force_reload: bool = False) -> int:
    """
    Ingests curated knowledge files from the /knowledge directory into the knowledge_chunks table.
    """
    if not force_reload:
        existing_count = db.query(KnowledgeChunk).count()
        if existing_count > 0:
            logger.info(f"Knowledge base already contains {existing_count} chunks. Skipping ingestion.")
            return existing_count

    inserted_count = 0

    # 1. Ingest bengaluru_civic_responsibilities.json
    civic_resp_path = KNOWLEDGE_DIR / "bengaluru_civic_responsibilities.json"
    if civic_resp_path.exists():
        with open(civic_resp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                text_to_embed = f"{item['title']} - {item['department']} - {item['jurisdiction']}: {item['content']}"
                embedding = await get_text_embedding(text_to_embed)
                
                last_ver = None
                if item.get("last_verified"):
                    try:
                        last_ver = datetime.fromisoformat(item["last_verified"].replace("Z", "+00:00"))
                    except Exception:
                        last_ver = datetime.now(timezone.utc)

                chunk = KnowledgeChunk(
                    title=item["title"],
                    department=item["department"],
                    jurisdiction=item["jurisdiction"],
                    source_url=item.get("source_url"),
                    text=item["content"],
                    embedding=embedding,
                    last_verified=last_ver,
                )
                db.add(chunk)
                inserted_count += 1

    # 2. Ingest citizen_charter_karnataka.json
    charter_path = KNOWLEDGE_DIR / "citizen_charter_karnataka.json"
    if charter_path.exists():
        try:
            with open(charter_path, "r", encoding="utf-8") as f:
                charter_data = json.load(f)
                services = charter_data if isinstance(charter_data, list) else charter_data.get("services", [])
                for s in services:
                    title = s.get("service_name", "Karnataka Citizen Charter Service")
                    dept = s.get("department", "Government of Karnataka")
                    content = (
                        f"Sakala Service: {title}. Department: {dept}. "
                        f"Stipulated Time Limit (SLA): {s.get('time_limit_days', s.get('sla_days', 'N/A'))} days. "
                        f"Designated Officer: {s.get('designated_officer', 'Competent Authority')}. "
                        f"Appellate Authority: {s.get('appellate_authority', 'Appellate Officer')}."
                    )
                    embedding = await get_text_embedding(content)
                    chunk = KnowledgeChunk(
                        title=title,
                        department=dept,
                        jurisdiction="Karnataka State / Bengaluru",
                        source_url=s.get("source_url", "https://sakala.kar.nic.in"),
                        text=content,
                        embedding=embedding,
                        last_verified=datetime.now(timezone.utc),
                    )
                    db.add(chunk)
                    inserted_count += 1
        except Exception as e:
            logger.warning(f"Error parsing citizen charter: {e}")

    # 3. Ingest SOP Markdown files
    for md_file in [KNOWLEDGE_DIR / "bbmp_garbage_swm_sop.md", KNOWLEDGE_DIR / "bbmp_drainage_sop.md"]:
        if md_file.exists():
            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem.replace("_", " ").title()
                dept = "BBMP SWM" if "swm" in md_file.stem or "garbage" in md_file.stem else "BBMP SWD"
                embedding = await get_text_embedding(content[:1000])
                chunk = KnowledgeChunk(
                    title=title,
                    department=dept,
                    jurisdiction="Bruhat Bengaluru Mahanagara Palike",
                    source_url="https://bbmp.gov.in/sop-guidelines",
                    text=content[:2000],
                    embedding=embedding,
                    last_verified=datetime.now(timezone.utc),
                )
                db.add(chunk)
                inserted_count += 1
            except Exception as e:
                logger.warning(f"Error parsing {md_file.name}: {e}")

    db.commit()
    logger.info(f"Successfully ingested {inserted_count} knowledge chunks.")
    return inserted_count


async def retrieve_knowledge(
    db: Session,
    query: str,
    top_k: int = 3,
    min_similarity_threshold: float = 0.25,
) -> Dict[str, Any]:
    """
    RAG retrieval: Queries knowledge chunks using hybrid vector + keyword matching.
    Returns chunk list with citation URLs and a flag indicating if retrieval is sufficient.
    """
    chunks: List[KnowledgeChunk] = db.query(KnowledgeChunk).all()
    if not chunks:
        # Try fast auto-ingest if empty
        await ingest_knowledge_seed(db)
        chunks = db.query(KnowledgeChunk).all()

    if not chunks:
        return {
            "query": query,
            "results": [],
            "is_sufficient": False,
            "explanation": "No knowledge chunks available in database.",
        }

    query_vec = await get_text_embedding(query)
    query_words = set(query.lower().split())

    scored_chunks: List[Tuple[float, KnowledgeChunk]] = []

    for chunk in chunks:
        # Vector score
        vec_score = 0.0
        if chunk.embedding:
            try:
                emb = chunk.embedding if isinstance(chunk.embedding, list) else json.loads(chunk.embedding)
                vec_score = cosine_similarity(query_vec, emb)
            except Exception:
                vec_score = 0.0

        # Keyword overlap boost
        chunk_text_lower = (chunk.title + " " + chunk.department + " " + chunk.text).lower()
        keyword_hits = sum(1 for w in query_words if len(w) > 3 and w in chunk_text_lower)
        keyword_score = min(keyword_hits * 0.15, 0.45)

        total_score = (vec_score * 0.7) + (keyword_score * 0.3)
        scored_chunks.append((total_score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_results = scored_chunks[:top_k]

    results_payload = []
    for score, chunk in top_results:
        results_payload.append({
            "chunk_id": chunk.id,
            "title": chunk.title,
            "department": chunk.department,
            "jurisdiction": chunk.jurisdiction,
            "source_url": chunk.source_url,
            "last_verified": chunk.last_verified.isoformat() if chunk.last_verified else None,
            "text": chunk.text,
            "relevance_score": round(score, 4),
        })

    is_sufficient = bool(top_results and top_results[0][0] >= min_similarity_threshold)

    return {
        "query": query,
        "results": results_payload,
        "is_sufficient": is_sufficient,
        "top_score": top_results[0][0] if top_results else 0.0,
    }
