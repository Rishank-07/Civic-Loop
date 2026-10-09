from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    case_id: Optional[int] = None
    title: str
    message: str
    channel: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
