from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.models.custom_types import CompatibleJSON


class TimelineEvent(Base):
    """
    Append-only timeline events table.
    Enforced by DB Trigger (trg_timeline_events_no_update / no_delete)
    and typed origins: SOURCE_FACT, USER_CLAIM, AI_RECOMMENDATION, SYSTEM_EVENT.
    """
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    origin = Column(
        String(50),
        nullable=False,
        index=True,
    )  # SOURCE_FACT, USER_CLAIM, AI_RECOMMENDATION, SYSTEM_EVENT
    actor = Column(String(150), nullable=False)
    source = Column(String(150), nullable=False)
    payload_json = Column(CompatibleJSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "origin IN ('SOURCE_FACT', 'USER_CLAIM', 'AI_RECOMMENDATION', 'SYSTEM_EVENT')",
            name="check_timeline_origin",
        ),
    )

    case = relationship("Case", back_populates="timeline_events")
