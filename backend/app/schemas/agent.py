from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AgentPlanRequest(BaseModel):
    user_goal: Optional[str] = Field(None, description="Optional custom goal or instruction.")


class AgentPlanResponse(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    reasoning: Optional[str] = None
    knowledge_context: Optional[Dict[str, Any]] = None


class AgentExecuteToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class AgentExecuteResponse(BaseModel):
    action_type: str
    tool_name: str
    result: Dict[str, Any]
