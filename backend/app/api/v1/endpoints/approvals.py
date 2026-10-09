from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.approval import Approval
from backend.app.schemas.approval import ApprovalResponse, ApprovalDecisionRequest
from backend.app.agent.executor import decide_approval

router = APIRouter()


@router.get("/cases/{case_id}/approvals", response_model=List[ApprovalResponse])
def list_case_approvals(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role not in ("OFFICER", "ADMIN") and case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    return db.query(Approval).filter(Approval.case_id == case_id).all()


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalResponse)
def handle_approval_decision(
    approval_id: int,
    request: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval record not found")

    case = approval.case
    if current_user.role not in ("OFFICER", "ADMIN") and case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    try:
        updated = decide_approval(
            approval_id=approval_id,
            decision=request.decision,
            user=current_user,
            db=db,
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
