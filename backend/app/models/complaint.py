from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.custom_types import CompatibleJSON


class ComplaintRecord(Base):
    """
    Immutable representation of an official or entered complaint.
    Original records are never overwritten.
    """
    __tablename__ = "complaint_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(100), nullable=False)  # e.g., BBMP Sahaaya 2.0, Swachhata, Namma Bengaluru
    external_id = Column(String(100), nullable=True, index=True)
    raw_text = Column(Text, nullable=False)
    official_status = Column(String(50), nullable=False)  # Stored separately from verification_state
    official_status_retrieved_at = Column(DateTime, nullable=True)
    retrieval_method = Column(
        String(50),
        nullable=False,
    )  # USER_ENTERED, IMPORTED_RECEIPT, SCREENSHOT_OCR, AUTHORISED_CONNECTOR, MOCK
    extracted_json = Column(CompatibleJSON, default=dict, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "retrieval_method IN ('USER_ENTERED', 'IMPORTED_RECEIPT', 'SCREENSHOT_OCR', 'AUTHORISED_CONNECTOR', 'MOCK')",
            name="check_complaint_retrieval_method",
        ),
    )

    case = relationship("Case", back_populates="complaint_records")


class CaseLinkSuggestion(Base):
    __tablename__ = "case_link_suggestions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_a = Column(Integer, ForeignKey("complaint_records.id", ondelete="CASCADE"), nullable=False)
    record_b = Column(Integer, ForeignKey("complaint_records.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, nullable=False)
    evidence_json = Column(CompatibleJSON, default=dict, nullable=False)
    status = Column(String(50), default="PROPOSED", nullable=False)  # PROPOSED, APPROVED, REJECTED
    decided_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PROPOSED', 'APPROVED', 'REJECTED')",
            name="check_link_suggestion_status",
        ),
    )
