from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.custom_types import CompatibleJSON


class Approval(Base):
    """
    Model for human-in-the-loop approvals before sensitive actions are executed.
    """
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)  # e.g., SUBMIT_BBMP_ESCALATION, DRAFT_RT_NOTICE
    draft_json = Column(CompatibleJSON, default=dict, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)  # PENDING, APPROVED, REJECTED
    decided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="check_approval_status",
        ),
    )

    case = relationship("Case", back_populates="approvals")
