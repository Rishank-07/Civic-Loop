from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    CaseResponse,
    CaseDetailResponse,
    VerificationTransitionRequest,
)
from backend.app.domain.state_machine import (
    VerificationStateMachine,
    InvalidStateTransitionError,
)
from backend.app.domain.timeline_service import record_event, TimelineOrigin

router = APIRouter()


def _check_case_access(case: Case, user: User):
    if user.role not in ("OFFICER", "ADMIN") and case.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this case.",
        )


@router.get("", response_model=List[CaseResponse])
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Case)
    if current_user.role not in ("OFFICER", "ADMIN"):
        query = query.filter(Case.user_id == current_user.id)

    if status_filter:
        query = query.filter(Case.status == status_filter.upper())

    return query.order_by(Case.created_at.desc()).all()


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    case_in: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = Case(
        user_id=current_user.id,
        title=case_in.title,
        issue_category=case_in.issue_category,
        location_text=case_in.location_text,
        lat=case_in.lat,
        lng=case_in.lng,
        ward=case_in.ward,
        jurisdiction=case_in.jurisdiction,
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # 1. Record canonical timeline creation event (Hard Constraint 8)
    record_event(
        db=db,
        case_id=case.id,
        event_type="CASE_CREATED",
        origin=TimelineOrigin.SYSTEM_EVENT,
        actor=f"Citizen ({current_user.name})",
        source="WebUI Intake",
        payload={
            "title": case.title,
            "ward": case.ward,
            "category": case.issue_category,
            "jurisdiction": case.jurisdiction,
        },
    )

    # 2. If an initial complaint was entered, store immutable complaint record
    if case_in.initial_complaint_raw_text:
        complaint = ComplaintRecord(
            case_id=case.id,
            source=case_in.initial_complaint_source or "User Entered",
            external_id=case_in.initial_external_id,
            raw_text=case_in.initial_complaint_raw_text,
            official_status="SUBMITTED",
            retrieval_method="USER_ENTERED",
            extracted_json={
                "initial_report": True,
                "ward": case.ward,
            },
            confidence=1.0,
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)

        record_event(
            db=db,
            case_id=case.id,
            event_type="COMPLAINT_RECORDED",
            origin=TimelineOrigin.USER_CLAIM,
            actor=current_user.name,
            source="Initial Intake Form",
            payload={
                "complaint_id": complaint.id,
                "source": complaint.source,
                "external_id": complaint.external_id,
            },
        )

    return case


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)
    return case


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: int,
    case_in: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    update_data = case_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)

    db.add(case)
    db.commit()
    db.refresh(case)

    record_event(
        db=db,
        case_id=case.id,
        event_type="CASE_METADATA_UPDATED",
        origin=TimelineOrigin.USER_CLAIM,
        actor=current_user.name,
        source="Case Management",
        payload=update_data,
    )

    return case


@router.post("/{case_id}/transition-verification", response_model=CaseResponse)
def transition_case_verification(
    case_id: int,
    transition_in: VerificationTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    origin = TimelineOrigin.USER_CLAIM if current_user.role == "CITIZEN" else TimelineOrigin.SYSTEM_EVENT

    try:
        updated_case = VerificationStateMachine.transition(
            case=case,
            new_state=transition_in.target_state,
            reason=transition_in.reason,
            actor=f"{current_user.name} ({current_user.role})",
            origin=origin,
            db=db,
        )
        return updated_case
    except InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "InvalidStateTransitionError",
                "message": str(exc),
                "from_state": exc.from_state,
                "to_state": exc.to_state,
                "allowed_transitions": list(exc.allowed),
            },
        )
