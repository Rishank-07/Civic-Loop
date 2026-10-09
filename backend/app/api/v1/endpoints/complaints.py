from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.schemas.complaint import (
    ComplaintRecordCreate,
    ComplaintRecordResponse,
)
from backend.app.domain.timeline_service import record_event, TimelineOrigin

router = APIRouter()


def _check_case_access(case: Case, user: User):
    if user.role not in ("OFFICER", "ADMIN") and case.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this case.",
        )


@router.post("/cases/{case_id}/complaints", response_model=ComplaintRecordResponse, status_code=status.HTTP_201_CREATED)
def add_complaint_record(
    case_id: int,
    record_in: ComplaintRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Appends an immutable complaint record to a case.
    Original records are never overwritten (Feature 2 / Hard Constraint 6).
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    origin = (
        TimelineOrigin.SOURCE_FACT
        if record_in.retrieval_method in ("AUTHORISED_CONNECTOR", "MOCK")
        else TimelineOrigin.USER_CLAIM
    )

    record = ComplaintRecord(
        case_id=case.id,
        source=record_in.source,
        external_id=record_in.external_id,
        raw_text=record_in.raw_text,
        official_status=record_in.official_status,
        official_status_retrieved_at=datetime.now(timezone.utc),
        retrieval_method=record_in.retrieval_method,
        extracted_json=record_in.extracted_json,
        confidence=record_in.confidence,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    record_event(
        db=db,
        case_id=case.id,
        event_type="COMPLAINT_RECORD_APPENDED",
        origin=origin,
        actor=f"{current_user.name} ({record_in.retrieval_method})",
        source=record_in.source,
        payload={
            "complaint_id": record.id,
            "external_id": record.external_id,
            "official_status": record.official_status,
            "retrieval_method": record.retrieval_method,
            "confidence": record.confidence,
        },
    )

    return record


@router.get("/cases/{case_id}/complaints", response_model=List[ComplaintRecordResponse])
def list_complaint_records(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    return (
        db.query(ComplaintRecord)
        .filter(ComplaintRecord.case_id == case_id)
        .order_by(ComplaintRecord.created_at.desc())
        .all()
    )
