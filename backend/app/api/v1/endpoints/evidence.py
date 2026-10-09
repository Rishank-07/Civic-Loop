from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.evidence import Evidence
from backend.app.schemas.evidence import EvidenceResponse
from backend.app.domain.evidence_service import save_and_process_evidence

router = APIRouter()


@router.post("/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_case_evidence(
    case_id: int,
    file: UploadFile = File(...),
    provenance: Optional[str] = Form("CITIZEN_CAMERA_UPLOAD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Uploads evidence photo privately, extracts EXIF metadata, and runs neutral vision analysis.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role not in ("OFFICER", "ADMIN") and case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        evidence = await save_and_process_evidence(
            db=db,
            case_id=case.id,
            file_bytes=content,
            filename=file.filename or "evidence.jpg",
            mime_type=file.content_type or "image/jpeg",
            user=current_user,
            provenance=provenance or "CITIZEN_CAMERA_UPLOAD",
        )
        return evidence
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process evidence: {str(exc)}")


@router.get("/cases/{case_id}/evidence", response_model=List[EvidenceResponse])
def list_case_evidence(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role not in ("OFFICER", "ADMIN") and case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")

    return (
        db.query(Evidence)
        .filter(Evidence.case_id == case_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )
