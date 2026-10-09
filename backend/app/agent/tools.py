"""
CivicLoop AI Agent Tool Registry
Defines 11 canonical agent tools with Pydantic parameter schemas, permission levels,
and external consequential flags according to the authoritative flowchart.
"""

from typing import Dict, Any, List, Optional, Type
from enum import Enum
from pydantic import BaseModel, Field


class ToolActionType(str, Enum):
    INFORMATION = "INFORMATION"
    FOLLOWUP_TASK = "FOLLOWUP_TASK"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"
    CLARIFICATION = "CLARIFICATION"


# -------------------------------------------------------------
# Pydantic Schemas for Tool Parameters
# -------------------------------------------------------------

class ClassifyIssueInput(BaseModel):
    text: str = Field(..., description="Raw complaint or incident text.")
    location: Optional[str] = Field(None, description="Location text or ward name.")


class LookupDepartmentResponsibilityInput(BaseModel):
    query: str = Field(..., description="Civic issue query or problem description.")
    ward: Optional[str] = Field(None, description="BBMP Ward number or name.")
    jurisdiction: Optional[str] = Field("Bengaluru Urban", description="Jurisdiction area.")


class RetrieveGuidanceInput(BaseModel):
    query: str = Field(..., description="Query for statutory rules, citizen charter, or SOP.")
    category: Optional[str] = Field(None, description="Category filter (GARBAGE, DRAINAGE, ROADS, etc.).")
    ward: Optional[str] = Field(None, description="Ward name or number.")


class RequestClarificationInput(BaseModel):
    question: str = Field(..., description="Clarifying question to ask the citizen.")
    missing_fields: List[str] = Field(default_factory=list, description="List of required fields missing from report.")


class DraftGrievanceInput(BaseModel):
    case_id: int = Field(..., description="Case ID for the grievance.")
    target_department: str = Field(..., description="Official department (e.g., BBMP SWM, BWSSB, BESCOM).")
    portal_name: str = Field(..., description="Target portal (e.g., BBMP Sahaaya 2.0, Swachhata, Sakala IPGRS).")
    grievance_text: str = Field(..., description="Formal grievance wording for portal submission.")
    urgency: Optional[str] = Field("NORMAL", description="Urgency level: NORMAL, HIGH, EMERGENCY.")


class DraftReferralInput(BaseModel):
    case_id: int = Field(..., description="Case ID for the inter-departmental referral.")
    from_department: str = Field(..., description="Transferring department (e.g. BBMP SWD).")
    to_department: str = Field(..., description="Receiving department (e.g. BWSSB Sewerage).")
    reason: str = Field(..., description="Statutory/technical reason for jurisdictional transfer.")


class ScheduleFollowupInput(BaseModel):
    case_id: int = Field(..., description="Case ID for follow-up.")
    task_type: str = Field(..., description="Task type (e.g., SYNC_EXTERNAL_STATUS, SEND_REMINDER).")
    delay_seconds: int = Field(3600, description="Delay in seconds before task runs.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task execution parameters.")


class CheckSourceStatusInput(BaseModel):
    case_id: int = Field(..., description="Case ID.")
    complaint_record_id: Optional[int] = Field(None, description="Specific complaint record ID to check.")
    connector_type: Optional[str] = Field("MOCK", description="Connector type (MOCK, MANUAL, PORTAL).")


class RequestCitizenVerificationInput(BaseModel):
    case_id: int = Field(..., description="Case ID.")
    message: str = Field(..., description="Message prompting citizen to verify resolution.")
    suggested_evidence_type: Optional[str] = Field("PHOTO_UPLOAD", description="Suggested evidence type.")


class RecordEventInput(BaseModel):
    case_id: int = Field(..., description="Case ID.")
    event_type: str = Field(..., description="Type of event to log.")
    origin: str = Field("AI_RECOMMENDATION", description="Origin (SOURCE_FACT, USER_CLAIM, AI_RECOMMENDATION, SYSTEM_EVENT).")
    actor: str = Field("CivicLoop Agent", description="Entity initiating the event.")
    source: str = Field("Agent Engine", description="Subsystem recording the event.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload.")


class SummariseTimelineInput(BaseModel):
    case_id: int = Field(..., description="Case ID whose timeline should be summarized.")


# -------------------------------------------------------------
# Tool Definition Class & Registry
# -------------------------------------------------------------

class AgentTool:
    def __init__(
        self,
        name: str,
        description: str,
        args_schema: Type[BaseModel],
        permission_level: str = "CITIZEN",
        external: bool = False,
        action_type: ToolActionType = ToolActionType.INFORMATION,
    ):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.permission_level = permission_level
        self.external = external
        self.action_type = action_type

    def to_openai_tool_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible tool definition for open-weight agent model."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }


TOOL_REGISTRY: Dict[str, AgentTool] = {
    "classify_issue": AgentTool(
        name="classify_issue",
        description="Classify raw text into civic category (GARBAGE, DRAINAGE, ROADS, OTHER) and candidate department.",
        args_schema=ClassifyIssueInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.INFORMATION,
    ),
    "lookup_department_responsibility": AgentTool(
        name="lookup_department_responsibility",
        description="Identify responsible civic agency (BBMP, BWSSB, BESCOM, BDA) with statutory citations.",
        args_schema=LookupDepartmentResponsibilityInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.INFORMATION,
    ),
    "retrieve_guidance": AgentTool(
        name="retrieve_guidance",
        description="Retrieve verified statutory rules, SOPs, and citizen charter SLAs from knowledge base with chunk citations.",
        args_schema=RetrieveGuidanceInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.INFORMATION,
    ),
    "request_clarification": AgentTool(
        name="request_clarification",
        description="Ask citizen to clarify missing required fields (location, photos, specific issue details) when information is insufficient.",
        args_schema=RequestClarificationInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.CLARIFICATION,
    ),
    "draft_grievance": AgentTool(
        name="draft_grievance",
        description="Prepare a formal grievance draft for submission to an external government portal. Consequential action requiring human approval.",
        args_schema=DraftGrievanceInput,
        permission_level="CITIZEN",
        external=True,
        action_type=ToolActionType.EXTERNAL_ACTION,
    ),
    "draft_referral": AgentTool(
        name="draft_referral",
        description="Prepare an official inter-departmental referral notice between civic agencies. Consequential action requiring approval.",
        args_schema=DraftReferralInput,
        permission_level="OFFICER",
        external=True,
        action_type=ToolActionType.EXTERNAL_ACTION,
    ),
    "schedule_followup": AgentTool(
        name="schedule_followup",
        description="Schedule an automated worker task to poll external portal status or remind the citizen.",
        args_schema=ScheduleFollowupInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.FOLLOWUP_TASK,
    ),
    "check_source_status": AgentTool(
        name="check_source_status",
        description="Query external portal connector for complaint status update.",
        args_schema=CheckSourceStatusInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.FOLLOWUP_TASK,
    ),
    "request_citizen_verification": AgentTool(
        name="request_citizen_verification",
        description="Request citizen outcome verification after administrative closure is recorded.",
        args_schema=RequestCitizenVerificationInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.CLARIFICATION,
    ),
    "record_event": AgentTool(
        name="record_event",
        description="Record an auditable observation or milestone into the case timeline.",
        args_schema=RecordEventInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.INFORMATION,
    ),
    "summarise_timeline": AgentTool(
        name="summarise_timeline",
        description="Generate an auditable, chronologically ordered summary of the case history.",
        args_schema=SummariseTimelineInput,
        permission_level="CITIZEN",
        external=False,
        action_type=ToolActionType.INFORMATION,
    ),
}


def get_all_tool_schemas() -> List[Dict[str, Any]]:
    return [tool.to_openai_tool_dict() for tool in TOOL_REGISTRY.values()]
