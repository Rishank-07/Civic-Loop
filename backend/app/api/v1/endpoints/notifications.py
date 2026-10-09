from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.schemas.notification import NotificationResponse
from backend.app.domain.notification_service import (
    get_user_notifications,
    mark_notification_read,
    MOCK_SENT_EMAILS,
)

router = APIRouter()


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_notifications(db=db, user_id=current_user.id)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = mark_notification_read(db=db, notification_id=notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return notif


@router.get("/mock-emails")
def get_mock_sent_emails(
    current_user: User = Depends(get_current_user),
):
    """Developer audit endpoint to inspect dispatched mock SMTP emails."""
    return {"count": len(MOCK_SENT_EMAILS), "emails": MOCK_SENT_EMAILS}
