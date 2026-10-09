from typing import Any, Dict, Optional
from enum import Enum
from sqlalchemy.orm import Session
from backend.app.models.case import Case
from backend.app.models.timeline import TimelineEvent


class TimelineOrigin(str, Enum):
    SOURCE_FACT = "SOURCE_FACT"
    USER_CLAIM = "USER_CLAIM"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class InvalidTimelineOriginError(ValueError):
    """Raised when an invalid origin is supplied for a timeline event."""
    def __init__(self, origin: str):
        super().__init__(
            f"Invalid timeline origin '{origin}'. Origin must be one of: "
            f"{[e.value for e in TimelineOrigin]}"
        )
        self.origin = origin


class CaseNotFoundError(Exception):
    """Raised when the specified case does not exist in the database."""
    def __init__(self, case_id: int):
        super().__init__(f"Case with ID {case_id} was not found.")
        self.case_id = case_id


def record_event(
    db: Session,
    case_id: int,
    event_type: str,
    origin: str | TimelineOrigin,
    actor: str,
    source: str,
    payload: Optional[Dict[str, Any]] = None,
) -> TimelineEvent:
    """
    The canonical service to write timeline events in CivicLoop.
    Every module MUST use this service to write timeline events (Hard Constraint 8).
    
    Enforces:
    1. Case existence.
    2. Strict origin validation (SOURCE_FACT, USER_CLAIM, AI_RECOMMENDATION, SYSTEM_EVENT).
    3. Immutability in downstream persistence.
    """
    origin_str = origin.value if isinstance(origin, TimelineOrigin) else str(origin)
    valid_origins = {e.value for e in TimelineOrigin}
    if origin_str not in valid_origins:
        raise InvalidTimelineOriginError(origin_str)

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise CaseNotFoundError(case_id)

    event = TimelineEvent(
        case_id=case_id,
        event_type=event_type,
        origin=origin_str,
        actor=actor,
        source=source,
        payload_json=payload or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
