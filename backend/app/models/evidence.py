from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.custom_types import CompatibleJSON


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    mime = Column(String(100), nullable=False)
    exif_json = Column(CompatibleJSON, default=dict, nullable=False)
    captured_at = Column(DateTime, nullable=True)
    supplied_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provenance = Column(String(150), nullable=False)  # e.g., CITIZEN_CAMERA_UPLOAD, FIELD_SURVEY
    ai_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    case = relationship("Case", back_populates="evidence_items")
