from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord, CaseLinkSuggestion
from backend.app.domain.case_linking import (
    compute_signals,
    get_embedding_safe,
    LinkEvaluationResult,
    AUTO_LINK_THRESHOLD,
    SUGGEST_LINK_THRESHOLD,
)
from backend.app.domain.timeline_service import record_event, TimelineOrigin

router = APIRouter()


class FindLinksRequest(BaseModel):
    category: str
    location_text: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    ward: Optional[str] = None
    reported_date: Optional[datetime] = None


from pydantic import BaseModel, ConfigDict, Field


class LinkSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_a: int
    record_b: int
    score: float
    evidence_json: dict
    status: str
    decided_by: Optional[int] = None
    decided_at: Optional[datetime] = None



class LinkComplaintToCaseRequest(BaseModel):
    complaint_id: int
    target_case_id: int
    reason: Optional[str] = None


@router.post("/find-links", response_model=List[LinkEvaluationResult])
async def find_case_links(
    payload: FindLinksRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluates an incoming complaint against active cases in the database
    and returns ranked link candidates with composite scores and explanations.
    """
    candidate_cases = (
        db.query(Case)
        .filter(Case.status.in_(["OPEN", "MONITORING"]))
        .order_by(Case.created_at.desc())
        .limit(30)
        .all()
    )

    if not candidate_cases:
        return []

    # Get query embedding
    query_text = f"{payload.category} at {payload.location_text} Ward: {payload.ward or 'unknown'}"
    complaint_embed = await get_embedding_safe(query_text)

    results: List[LinkEvaluationResult] = []

    for c in candidate_cases:
        case_text = f"{c.issue_category} at {c.location_text} Ward: {c.ward}"
        case_embed = await get_embedding_safe(case_text)

        score, signals, explanation = compute_signals(
            complaint_category=payload.category,
            complaint_location_text=payload.location_text,
            complaint_lat=payload.lat,
            complaint_lng=payload.lng,
            complaint_ward=payload.ward,
            complaint_date=payload.reported_date or datetime.now(timezone.utc),
            complaint_embed=complaint_embed,
            case_category=c.issue_category,
            case_location_text=c.location_text,
            case_lat=c.lat,
            case_lng=c.lng,
            case_ward=c.ward,
            case_date=c.created_at,
            case_embed=case_embed,
        )

        if score >= SUGGEST_LINK_THRESHOLD:
            conf_level = "AUTO_LINK" if score >= AUTO_LINK_THRESHOLD else "SUGGEST_LINK"
            results.append(
                LinkEvaluationResult(
                    case_id=c.id,
                    case_title=c.title,
                    composite_score=score,
                    confidence_level=conf_level,
                    explanation=explanation,
                    signals=signals,
                )
            )

    results.sort(key=lambda x: x.composite_score, reverse=True)
    return results


@router.post("/link-complaint", status_code=status.HTTP_200_OK)
def link_complaint_to_case(
    payload: LinkComplaintToCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Attaches an existing complaint record to a target persistent case,
    preserving full audit trail and creating a timeline event.
    """
    complaint = db.query(ComplaintRecord).filter(ComplaintRecord.id == payload.complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint record not found")

    target_case = db.query(Case).filter(Case.id == payload.target_case_id).first()
    if not target_case:
        raise HTTPException(status_code=404, detail="Target case not found")

    old_case_id = complaint.case_id
    complaint.case_id = target_case.id
    db.commit()

    record_event(
        db=db,
        case_id=target_case.id,
        event_type="CROSS_PORTAL_COMPLAINT_LINKED",
        origin=TimelineOrigin.AI_AGENT,
        actor=f"{current_user.name} ({current_user.role})",
        source=complaint.source,
        payload={
            "complaint_id": complaint.id,
            "external_id": complaint.external_id,
            "previous_case_id": old_case_id,
            "reason": payload.reason or "Cross-portal continuity linking",
        },
    )

    return {
        "status": "success",
        "message": f"Complaint #{complaint.id} ({complaint.source}) successfully linked to Case #{target_case.id}",
    }


@router.get("/cases/{case_id}/suggestions", response_model=List[LinkSuggestionResponse])
def get_case_link_suggestions(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves cross-portal link suggestions associated with complaints in this case.
    """
    complaints = db.query(ComplaintRecord).filter(ComplaintRecord.case_id == case_id).all()
    complaint_ids = [c.id for c in complaints]

    if not complaint_ids:
        return []

    suggestions = (
        db.query(CaseLinkSuggestion)
        .filter(
            (CaseLinkSuggestion.record_a.in_(complaint_ids))
            | (CaseLinkSuggestion.record_b.in_(complaint_ids))
        )
        .all()
    )
    return suggestions
