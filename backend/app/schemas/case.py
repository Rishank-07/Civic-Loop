from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.complaint import ComplaintRecordResponse
from backend.app.schemas.timeline import TimelineEventResponse

IssueCategoryType = Literal["GARBAGE", "DRAINAGE", "OTHER"]
CaseStatusType = Literal["OPEN", "MONITORING", "CLOSED"]
VerificationStateType = Literal[
    "AWAITING_VERIFICATION",
    "CITIZEN_CONFIRMED_RESOLVED",
    "RESOLUTION_DISPUTED",
    "INSUFFICIENT_EVIDENCE",
]


class CaseBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    issue_category: IssueCategoryType
    location_text: str = Field(..., min_length=3, max_length=500)
    lat: Optional[float] = None
    lng: Optional[float] = None
    ward: str = Field(..., min_length=2, max_length=100)
    jurisdiction: str = Field(..., min_length=2, max_length=150)


class CaseCreate(CaseBase):
    initial_complaint_raw_text: Optional[str] = None
    initial_complaint_source: Optional[str] = "BBMP Sahaaya 2.0"
    initial_external_id: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[CaseStatusType] = None
    location_text: Optional[str] = None
    ward: Optional[str] = None
    jurisdiction: Optional[str] = None


class VerificationTransitionRequest(BaseModel):
    target_state: VerificationStateType
    reason: str = Field(..., min_length=5)


class CaseResponse(CaseBase):
    id: int
    user_id: int
    status: CaseStatusType
    verification_state: VerificationStateType
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseDetailResponse(CaseResponse):
    complaint_records: List[ComplaintRecordResponse] = []
    timeline_events: List[TimelineEventResponse] = []
