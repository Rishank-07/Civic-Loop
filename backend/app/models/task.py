from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.custom_types import CompatibleJSON


class Task(Base):
    """
    Background tasks table ensuring idempotency and retry semantics.
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    task_type = Column(String(100), nullable=False)
    status = Column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )  # PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    last_error = Column(Text, nullable=True)
    payload_json = Column(CompatibleJSON, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="check_task_status",
        ),
    )

    case = relationship("Case", back_populates="tasks")
