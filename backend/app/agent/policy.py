"""
CivicLoop AI Agent Policy Layer
Enforces deterministic safety constraints, permission checks, and state machine boundaries
on model-proposed actions. Logs rejections to the case timeline as SYSTEM_EVENT.
"""

from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.user import User
from backend.app.agent.tools import TOOL_REGISTRY, AgentTool
from backend.app.domain.timeline_service import record_event, TimelineOrigin


class PolicyViolationError(ValueError):
    """Raised when an agent action violates safety or state machine policy."""
    def __init__(self, message: str, tool_name: str, case_id: Optional[int] = None):
        super().__init__(message)
        self.tool_name = tool_name
        self.case_id = case_id


class AgentPolicyLayer:
    """
    Guards execution of tool calls proposed by the AI planner.
    """

    ROLE_HIERARCHY = {
        "CITIZEN": 1,
        "OFFICER": 2,
        "ADMIN": 3,
        "SYSTEM": 4,
    }

    @classmethod
    def validate_action(
        cls,
        tool_name: str,
        arguments: Dict[str, Any],
        case: Optional[Case],
        user: Optional[User],
        db: Session,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates if the requested tool action is permissible under the current case state and user role.
        If rejected, writes a SYSTEM_EVENT rejection record to the timeline.
        """
        tool = TOOL_REGISTRY.get(tool_name)
        if not tool:
            cls._log_rejection(
                db=db,
                case_id=case.id if case else None,
                tool_name=tool_name,
                reason=f"Unknown tool '{tool_name}'",
                actor=user.name if user else "AI Agent",
            )
            return False, f"Unknown tool: '{tool_name}'"

        # 1. User Permission Level Check
        user_role = user.role if user else "CITIZEN"
        user_rank = cls.ROLE_HIERARCHY.get(user_role, 1)
        tool_rank = cls.ROLE_HIERARCHY.get(tool.permission_level, 1)

        if user_rank < tool_rank:
            reason = f"Role '{user_role}' lacks permission for tool '{tool_name}' (requires '{tool.permission_level}')"
            cls._log_rejection(
                db=db,
                case_id=case.id if case else None,
                tool_name=tool_name,
                reason=reason,
                actor=user.name if user else "AI Agent",
            )
            return False, reason

        # 2. Case State Constraints
        if case:
            # Closed case protection
            if case.status == "CLOSED" and case.verification_state == "CITIZEN_CONFIRMED_RESOLVED":
                if tool.action_type in ("FOLLOWUP_TASK", "EXTERNAL_ACTION"):
                    reason = f"Action '{tool_name}' not permitted on CLOSED case with confirmed resolution."
                    cls._log_rejection(
                        db=db,
                        case_id=case.id,
                        tool_name=tool_name,
                        reason=reason,
                        actor=user.name if user else "AI Agent",
                    )
                    return False, reason

            # Verification request gating: can only request verification if case is open/monitoring or closure was reported
            if tool_name == "request_citizen_verification" and case.verification_state == "CITIZEN_CONFIRMED_RESOLVED":
                reason = "Cannot request citizen verification on an already confirmed resolved case."
                cls._log_rejection(
                    db=db,
                    case_id=case.id,
                    tool_name=tool_name,
                    reason=reason,
                    actor=user.name if user else "AI Agent",
                )
                return False, reason

        return True, None

    @classmethod
    def _log_rejection(
        cls,
        db: Session,
        case_id: Optional[int],
        tool_name: str,
        reason: str,
        actor: str = "AI Agent",
    ):
        if case_id:
            try:
                record_event(
                    db=db,
                    case_id=case_id,
                    event_type="POLICY_REJECTION",
                    origin=TimelineOrigin.SYSTEM_EVENT,
                    actor=actor,
                    source="Agent Policy Engine",
                    payload={
                        "attempted_tool": tool_name,
                        "rejection_reason": reason,
                    },
                )
            except Exception as e:
                pass
