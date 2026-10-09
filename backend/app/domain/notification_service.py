"""
CivicLoop Notification Service (Feature 4)
Handles in-app notifications and email dispatching via an auditable SMTP stub.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.notification import Notification
from backend.app.models.user import User

logger = logging.getLogger(__name__)

# In-memory stub log of dispatched emails for test assertions and auditability
MOCK_SENT_EMAILS: List[Dict[str, Any]] = []


def send_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    case_id: Optional[int] = None,
    channel: str = "IN_APP",
    send_email_copy: bool = True,
) -> Notification:
    """
    Creates an in-app notification record and optionally dispatches via the SMTP stub.
    """
    notif = Notification(
        user_id=user_id,
        case_id=case_id,
        title=title,
        message=message,
        channel=channel,
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    user = db.query(User).filter(User.id == user_id).first()
    recipient_email = user.email if user else f"user_{user_id}@example.com"

    if send_email_copy:
        email_record = {
            "to": recipient_email,
            "subject": f"[CivicLoop] {title}",
            "body": message,
            "case_id": case_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notification_id": notif.id,
        }
        MOCK_SENT_EMAILS.append(email_record)
        logger.info(f"Mock SMTP: Sent email to {recipient_email} - Subject: '{title}'")

    return notif


def get_user_notifications(db: Session, user_id: int) -> List[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def mark_notification_read(db: Session, notification_id: int) -> Optional[Notification]:
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif:
        notif.is_read = True
        db.commit()
        db.refresh(notif)
    return notif
