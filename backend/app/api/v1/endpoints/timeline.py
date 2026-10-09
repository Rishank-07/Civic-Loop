from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.timeline import TimelineEvent
from backend.app.schemas.timeline import TimelineEventResponse
from backend.app.domain.timeline_service import TimelineOrigin

router = APIRouter()


def _check_case_access(case: Case, user: User):
    if user.role not in ("OFFICER", "ADMIN") and case.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this case's timeline.",
        )


@router.get("/cases/{case_id}/timeline", response_model=List[TimelineEventResponse])
def get_case_timeline(
    case_id: int,
    origin: Optional[str] = Query(
        None,
        description="Filter events by origin: SOURCE_FACT, USER_CLAIM, AI_RECOMMENDATION, SYSTEM_EVENT",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the auditable timeline of events for a case,
    with origin filtering and per-user permission checks.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    query = db.query(TimelineEvent).filter(TimelineEvent.case_id == case_id)

    if origin:
        origin_upper = origin.upper()
        valid_origins = {e.value for e in TimelineOrigin}
        if origin_upper not in valid_origins:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid origin filter '{origin}'. Must be one of: {list(valid_origins)}",
            )
        query = query.filter(TimelineEvent.origin == origin_upper)

    return query.order_by(TimelineEvent.created_at.asc()).all()
