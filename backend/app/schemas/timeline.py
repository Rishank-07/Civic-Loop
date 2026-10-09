from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict
from backend.app.domain.timeline_service import TimelineOrigin


class TimelineEventBase(BaseModel):
    event_type: str
    origin: TimelineOrigin
    actor: str
    source: str
    payload_json: Dict[str, Any] = {}


class TimelineEventCreate(TimelineEventBase):
    pass


class TimelineEventResponse(TimelineEventBase):
    id: int
    case_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
