from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.schemas.knowledge import KnowledgeSearchResponse, KnowledgeChunkResponse
from backend.app.domain.knowledge_service import retrieve_knowledge, ingest_knowledge_seed

router = APIRouter()


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_base(
    query: str = Query(..., min_length=2),
    top_k: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    RAG search against verified civic knowledge chunks with citations and source URLs.
    """
    res = await retrieve_knowledge(db=db, query=query, top_k=top_k)
    return KnowledgeSearchResponse(
        query=res["query"],
        is_sufficient=res["is_sufficient"],
        top_score=res.get("top_score"),
        results=[KnowledgeChunkResponse(**r) for r in res["results"]],
    )


@router.post("/ingest")
async def trigger_ingestion(
    force_reload: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-ingests curated knowledge seed documents from /knowledge into the database.
    """
    count = await ingest_knowledge_seed(db=db, force_reload=force_reload)
    return {"status": "success", "ingested_chunks_count": count}
