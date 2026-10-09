"""
CivicLoop External Portal Connectors (Feature 4)
Defines connector interface for public grievance portals with status outcomes:
{OK, UNAVAILABLE, INVALID, STALE}.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from backend.app.models.complaint import ComplaintRecord


class StatusOutcome(str, Enum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    STALE = "STALE"


class StatusResult(BaseModel):
    outcome: StatusOutcome
    external_status: str
    is_closure: bool = False
    source_label: str
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    message: str


class BasePortalConnector(ABC):
    """
    Abstract interface for civic portal status checks.
    """

    @abstractmethod
    def check_status(self, complaint_record: ComplaintRecord) -> StatusResult:
        """
        Queries the portal for the official status of the given complaint record.
        """
        pass
