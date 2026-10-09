from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class KnowledgeChunkResponse(BaseModel):
    chunk_id: int
    title: str
    department: str
    jurisdiction: str
    source_url: Optional[str] = None
    last_verified: Optional[str] = None
    text: str
    relevance_score: Optional[float] = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    is_sufficient: bool
    top_score: Optional[float] = None
    results: List[KnowledgeChunkResponse]
