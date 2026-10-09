from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from backend.app.core.database import Base


class AICall(Base):
    """
    Audit log for every open-weight model invocation.
    Logs model identity, purpose, latency, token counts, and validation status
    WITHOUT storing sensitive content unnecessarily (Hard Constraint 6).
    """
    __tablename__ = "ai_calls"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model = Column(String(150), nullable=False, index=True)
    purpose = Column(String(150), nullable=False, index=True)  # e.g. "extraction", "linking_explanation", "embedding"
    latency_ms = Column(Float, nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    validated = Column(Boolean, nullable=False, default=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
