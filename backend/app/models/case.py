from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    issue_category = Column(String(50), nullable=False)  # GARBAGE, DRAINAGE, OTHER
    location_text = Column(String(500), nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    ward = Column(String(100), nullable=False)
    jurisdiction = Column(String(150), nullable=False)
    status = Column(String(50), nullable=False, default="OPEN")  # OPEN, MONITORING, CLOSED
    verification_state = Column(
        String(50),
        nullable=False,
        default="AWAITING_VERIFICATION",
    )  # AWAITING_VERIFICATION, CITIZEN_CONFIRMED_RESOLVED, RESOLUTION_DISPUTED, INSUFFICIENT_EVIDENCE
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "issue_category IN ('GARBAGE', 'DRAINAGE', 'OTHER')",
            name="check_case_issue_category",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'MONITORING', 'CLOSED')",
            name="check_case_status",
        ),
        CheckConstraint(
            "verification_state IN ('AWAITING_VERIFICATION', 'CITIZEN_CONFIRMED_RESOLVED', 'RESOLUTION_DISPUTED', 'INSUFFICIENT_EVIDENCE')",
            name="check_case_verification_state",
        ),
    )

    # Relationships
    user = relationship("User", back_populates="cases")
    complaint_records = relationship("ComplaintRecord", back_populates="case", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="case", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="case", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="case", cascade="all, delete-orphan")
