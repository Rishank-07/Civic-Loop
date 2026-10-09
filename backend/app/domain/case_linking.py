"""
CivicLoop Feature 1: Cross-Portal Case Continuity & Linking Engine
==================================================================
Combines open-weight semantic embeddings (Qwen3-Embedding / BGE-M3) with
deterministic geospatial and metadata rules to link complaints across
BBMP Sahaaya, Swachhata, BESCOM Namma 1912, and BWSSB into single persistent cases.

HARD CONSTRAINTS ENFORCED:
- Uses ONLY open-weight embedding representations.
- Produces auditable deterministic scores and natural language explanations.
- Never overwrites historical records.
"""

import math
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.ai.llm import llm_client

logger = logging.getLogger(__name__)

# Configurable Weights for Composite Link Scoring
WEIGHT_EMBEDDING = 0.35
WEIGHT_GEOSPATIAL = 0.30
WEIGHT_CATEGORY = 0.20
WEIGHT_WARD = 0.10
WEIGHT_RECENCY = 0.05

# Thresholds
AUTO_LINK_THRESHOLD = 0.78
SUGGEST_LINK_THRESHOLD = 0.50
MAX_GEO_DISTANCE_METERS = 500.0  # Max distance to consider for geospatial proximity


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in meters between two points on the earth.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Computes cosine similarity between two float vectors.
    """
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    sim = dot / (norm1 * norm2)
    return max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0 else sim))


import hashlib


def get_deterministic_text_embedding(text: str, dim: int = 256) -> List[float]:
    """Deterministic fallback text embedding based on stable md5 hashing."""
    tokens = text.lower().split()
    vec = [0.0] * dim
    for i, token in enumerate(tokens):
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0 / (1.0 + (i * 0.1))
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec



class MatchSignals(BaseModel):
    embedding_similarity: float = 0.0
    geo_distance_meters: Optional[float] = None
    geo_similarity: float = 0.0
    category_match: bool = False
    category_similarity: float = 0.0
    ward_match: bool = False
    ward_similarity: float = 0.0
    time_diff_days: Optional[float] = None
    recency_similarity: float = 0.0


class LinkEvaluationResult(BaseModel):
    case_id: int
    case_title: str
    composite_score: float
    confidence_level: str  # AUTO_LINK, SUGGEST_LINK, UNRELATED
    explanation: str
    signals: MatchSignals


def compute_signals(
    complaint_category: str,
    complaint_location_text: str,
    complaint_lat: Optional[float],
    complaint_lng: Optional[float],
    complaint_ward: Optional[str],
    complaint_date: Optional[datetime],
    complaint_embed: Optional[List[float]],
    case_category: str,
    case_location_text: str,
    case_lat: Optional[float],
    case_lng: Optional[float],
    case_ward: Optional[str],
    case_date: Optional[datetime],
    case_embed: Optional[List[float]],
) -> Tuple[float, MatchSignals, str]:
    """
    Computes deterministic match signals and composite score between a complaint and a case.
    """
    signals = MatchSignals()
    explanation_parts = []

    # 1. Embedding Similarity
    if complaint_embed and case_embed:
        signals.embedding_similarity = cosine_similarity(complaint_embed, case_embed)
    else:
        # Text heuristic comparison
        c_words = set(complaint_location_text.lower().split())
        case_words = set(case_location_text.lower().split())
        overlap = len(c_words.intersection(case_words))
        total = max(1, len(c_words.union(case_words)))
        signals.embedding_similarity = overlap / total

    # 2. Geospatial Proximity
    has_coords = (
        complaint_lat is not None
        and complaint_lng is not None
        and case_lat is not None
        and case_lng is not None
    )
    if has_coords:
        dist_m = haversine_distance_meters(
            complaint_lat, complaint_lng, case_lat, case_lng  # type: ignore[arg-type]
        )
        signals.geo_distance_meters = round(dist_m, 1)
        if dist_m <= 30.0:
            signals.geo_similarity = 1.0
            explanation_parts.append(f"exact GPS match ({round(dist_m)}m apart)")
        elif dist_m <= MAX_GEO_DISTANCE_METERS:
            signals.geo_similarity = max(0.0, 1.0 - (dist_m / MAX_GEO_DISTANCE_METERS))
            explanation_parts.append(f"close physical proximity ({round(dist_m)}m apart)")
        else:
            signals.geo_similarity = 0.0
    else:
        # Fallback to location string matching
        signals.geo_similarity = signals.embedding_similarity * 0.7

    # 3. Category Match
    c_cat = (complaint_category or "").upper().strip()
    k_cat = (case_category or "").upper().strip()
    if c_cat == k_cat and c_cat in ("GARBAGE", "DRAINAGE", "OTHER"):
        signals.category_match = True
        signals.category_similarity = 1.0
        explanation_parts.append(f"matching issue category '{c_cat}'")
    elif (c_cat == "GARBAGE" and "waste" in case_location_text.lower()) or (
        c_cat == "DRAINAGE" and "drain" in case_location_text.lower()
    ):
        signals.category_similarity = 0.7
        explanation_parts.append(f"closely related civic problem domain")
    else:
        signals.category_match = False
        signals.category_similarity = 0.1

    # 4. Ward Match
    import re
    w1 = (complaint_ward or "").strip().lower()
    w2 = (case_ward or "").strip().lower()
    w1_nums = set(re.findall(r"\d+", w1))
    w2_nums = set(re.findall(r"\d+", w2))
    
    if w1_nums and w2_nums and w1_nums.intersection(w2_nums):
        signals.ward_match = True
        signals.ward_similarity = 1.0
        explanation_parts.append(f"same administrative ward '{complaint_ward}'")
    else:
        # Check area token overlap ignoring generic administrative stopwords
        stopwords = {"ward", "zone", "road", "main", "cross", "stage", "block", "layout", "near", "east", "west", "north", "south"}
        tokens1 = {t for t in re.findall(r"\b\w{4,}\b", w1) if t not in stopwords}
        tokens2 = {t for t in re.findall(r"\b\w{4,}\b", w2) if t not in stopwords}
        if tokens1 and tokens2 and tokens1.intersection(tokens2):
            signals.ward_match = True
            signals.ward_similarity = 0.8
            explanation_parts.append(f"matching area '{complaint_ward}'")
        else:
            signals.ward_similarity = 0.0



    # 5. Temporal Recency
    if complaint_date and case_date:
        d1 = complaint_date if complaint_date.tzinfo else complaint_date.replace(tzinfo=timezone.utc)
        d2 = case_date if case_date.tzinfo else case_date.replace(tzinfo=timezone.utc)
        diff_days = abs((d1 - d2).total_seconds()) / 86400.0
        signals.time_diff_days = round(diff_days, 1)
        if diff_days <= 2.0:
            signals.recency_similarity = 1.0
            explanation_parts.append(f"reported within 48 hours")
        elif diff_days <= 14.0:
            signals.recency_similarity = max(0.0, 1.0 - (diff_days / 14.0))
            explanation_parts.append(f"reported within {round(diff_days)} days")
        elif diff_days <= 60.0:
            signals.recency_similarity = 0.3
        else:
            signals.recency_similarity = 0.0
    else:
        signals.recency_similarity = 0.5


    # Calculate Weighted Composite Score
    composite_score = (
        (WEIGHT_EMBEDDING * signals.embedding_similarity)
        + (WEIGHT_GEOSPATIAL * signals.geo_similarity)
        + (WEIGHT_CATEGORY * signals.category_similarity)
        + (WEIGHT_WARD * signals.ward_similarity)
        + (WEIGHT_RECENCY * signals.recency_similarity)
    )
    composite_score = round(min(1.0, max(0.0, composite_score)), 3)

    # Generate natural language explanation
    if explanation_parts:
        explanation = f"Match confidence {int(composite_score * 100)}% based on " + ", ".join(explanation_parts) + "."
    else:
        explanation = f"Match confidence {int(composite_score * 100)}% based on general metadata similarity."

    return composite_score, signals, explanation


async def get_embedding_safe(text: str) -> List[float]:
    """Generates embedding using open-weight embedding model with fallback."""
    try:
        return await llm_client.embed(text=text, purpose="case_linking")
    except Exception as e:
        logger.warning(f"Live embedding failed ({e}), using deterministic vector representation")
        return get_deterministic_text_embedding(text)
