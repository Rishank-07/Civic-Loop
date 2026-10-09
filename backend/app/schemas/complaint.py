from datetime import datetime
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


RetrievalMethodType = Literal[
    "USER_ENTERED",
    "IMPORTED_RECEIPT",
    "SCREENSHOT_OCR",
    "AUTHORISED_CONNECTOR",
    "MOCK",
]


class ComplaintRecordBase(BaseModel):
    source: str
    external_id: Optional[str] = None
    raw_text: str
    official_status: str
    retrieval_method: RetrievalMethodType = "USER_ENTERED"
    extracted_json: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ComplaintRecordCreate(ComplaintRecordBase):
    pass


class ComplaintRecordResponse(ComplaintRecordBase):
    id: int
    case_id: int
    official_status_retrieved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
