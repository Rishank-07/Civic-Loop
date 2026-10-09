from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EvidenceResponse(BaseModel):
    id: int
    case_id: int
    file_path: str
    mime: str
    exif_json: Dict[str, Any]
    captured_at: Optional[datetime] = None
    supplied_by: Optional[int] = None
    provenance: str
    ai_description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
