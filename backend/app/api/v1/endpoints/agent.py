from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.schemas.agent import (
    AgentPlanRequest,
    AgentPlanResponse,
    AgentExecuteToolRequest,
    AgentExecuteResponse,
)
from backend.app.agent.planner import plan_next_action
from backend.app.agent.executor import execute_agent_tool
from backend.app.agent.policy import PolicyViolationError

router = APIRouter()


def _check_case_access(case: Case, user: User):
    if user.role not in ("OFFICER", "ADMIN") and case.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this case.",
        )


@router.post("/cases/{case_id}/plan", response_model=AgentPlanResponse)
async def get_agent_plan(
    case_id: int,
    request: AgentPlanRequest = AgentPlanRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Asks the open-weight agent model to analyze case state and recommend ONE next action.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    plan = await plan_next_action(case=case, db=db, user_goal=request.user_goal)
    return AgentPlanResponse(
        tool_name=plan["tool_name"],
        arguments=plan["arguments"],
        reasoning=plan.get("reasoning"),
        knowledge_context=plan.get("knowledge_context"),
    )


@router.post("/cases/{case_id}/step", response_model=AgentExecuteResponse)
async def run_agent_step(
    case_id: int,
    request: AgentPlanRequest = AgentPlanRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Autonomous agent step: plans next tool action, validates against policy, and executes it.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    plan = await plan_next_action(case=case, db=db, user_goal=request.user_goal)

    try:
        exec_result = await execute_agent_tool(
            tool_name=plan["tool_name"],
            arguments=plan["arguments"],
            case_id=case.id,
            user=current_user,
            db=db,
        )
        return AgentExecuteResponse(
            action_type=exec_result.get("action_type", "INFORMATION"),
            tool_name=plan["tool_name"],
            result=exec_result,
        )
    except PolicyViolationError as pve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "PolicyViolationError", "message": str(pve), "tool": plan["tool_name"]},
        )


@router.post("/cases/{case_id}/execute-tool", response_model=AgentExecuteResponse)
async def execute_tool_directly(
    case_id: int,
    request: AgentExecuteToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes a specific registered tool against the case with policy validation.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    _check_case_access(case, current_user)

    try:
        exec_result = await execute_agent_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            case_id=case.id,
            user=current_user,
            db=db,
        )
        return AgentExecuteResponse(
            action_type=exec_result.get("action_type", "INFORMATION"),
            tool_name=request.tool_name,
            result=exec_result,
        )
    except PolicyViolationError as pve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "PolicyViolationError", "message": str(pve), "tool": request.tool_name},
        )
