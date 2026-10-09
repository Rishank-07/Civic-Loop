from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="Decision: APPROVED or REJECTED")


class ApprovalResponse(BaseModel):
    id: int
    case_id: int
    action_type: str
    draft_json: Dict[str, Any]
    status: str
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
