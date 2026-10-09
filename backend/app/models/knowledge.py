from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from backend.app.core.database import Base
from backend.app.models.custom_types import CompatibleVector


class KnowledgeChunk(Base):
    """
    Curated civic knowledge chunks embedded with open-weight models (BGE-M3 / Qwen3).
    Used to ground agent advice in official BBMP / Sakala rules without hallucinating.
    """
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_url = Column(String(500), nullable=True)
    title = Column(String(255), nullable=False)
    department = Column(String(150), nullable=False)  # BBMP SWM, BBMP SWD, BWSSB, etc.
    jurisdiction = Column(String(150), nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(CompatibleVector(dim=768), nullable=True)
    last_verified = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
