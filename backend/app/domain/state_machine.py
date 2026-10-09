from enum import Enum
from typing import Dict, Set, Optional
from sqlalchemy.orm import Session
from backend.app.models.case import Case
from backend.app.domain.timeline_service import record_event, TimelineOrigin


class VerificationState(str, Enum):
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    CITIZEN_CONFIRMED_RESOLVED = "CITIZEN_CONFIRMED_RESOLVED"
    RESOLUTION_DISPUTED = "RESOLUTION_DISPUTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal verification state transition is attempted."""
    def __init__(self, from_state: str, to_state: str, allowed: Set[str]):
        super().__init__(
            f"Illegal state transition from '{from_state}' to '{to_state}'. "
            f"Allowed target states are: {sorted(list(allowed))}"
        )
        self.from_state = from_state
        self.to_state = to_state
        self.allowed = allowed


class VerificationStateMachine:
    """
    Deterministic Verification State Machine.
    Controls CivicLoop's independent citizen verification state, separate
    from official government portal statuses (Honesty Rule 6).
    """

    TRANSITIONS: Dict[VerificationState, Set[VerificationState]] = {
        VerificationState.AWAITING_VERIFICATION: {
            VerificationState.CITIZEN_CONFIRMED_RESOLVED,
            VerificationState.RESOLUTION_DISPUTED,
            VerificationState.INSUFFICIENT_EVIDENCE,
        },
        VerificationState.INSUFFICIENT_EVIDENCE: {
            VerificationState.AWAITING_VERIFICATION,
            VerificationState.CITIZEN_CONFIRMED_RESOLVED,
            VerificationState.RESOLUTION_DISPUTED,
        },
        VerificationState.RESOLUTION_DISPUTED: {
            VerificationState.AWAITING_VERIFICATION,
            VerificationState.CITIZEN_CONFIRMED_RESOLVED,
        },
        VerificationState.CITIZEN_CONFIRMED_RESOLVED: {
            VerificationState.RESOLUTION_DISPUTED,
            VerificationState.AWAITING_VERIFICATION,
        },
    }

    @classmethod
    def get_allowed_transitions(cls, current_state: str | VerificationState) -> Set[str]:
        state_enum = current_state if isinstance(current_state, VerificationState) else VerificationState(current_state)
        allowed = cls.TRANSITIONS.get(state_enum, set())
        return {s.value for s in allowed}

    @classmethod
    def can_transition(
        cls,
        current_state: str | VerificationState,
        target_state: str | VerificationState,
    ) -> bool:
        try:
            curr = current_state if isinstance(current_state, VerificationState) else VerificationState(current_state)
            target = target_state if isinstance(target_state, VerificationState) else VerificationState(target_state)
        except ValueError:
            return False

        allowed = cls.TRANSITIONS.get(curr, set())
        return target in allowed

    @classmethod
    def transition(
        cls,
        case: Case,
        new_state: str | VerificationState,
        reason: str,
        actor: str,
        origin: str | TimelineOrigin = TimelineOrigin.SYSTEM_EVENT,
        db: Optional[Session] = None,
    ) -> Case:
        """
        Executes a validated verification-state transition.
        Rejects invalid transitions with InvalidStateTransitionError.
        Records an auditable event in the timeline.
        """
        curr_enum = VerificationState(case.verification_state)
        target_enum = new_state if isinstance(new_state, VerificationState) else VerificationState(new_state)

        allowed = cls.TRANSITIONS.get(curr_enum, set())
        allowed_str = {s.value for s in allowed}

        if target_enum not in allowed:
            raise InvalidStateTransitionError(
                from_state=curr_enum.value,
                to_state=target_enum.value,
                allowed=allowed_str,
            )

        old_state = case.verification_state
        case.verification_state = target_enum.value

        # Automatically coordinate overall case status if resolved
        if target_enum == VerificationState.CITIZEN_CONFIRMED_RESOLVED:
            case.status = "CLOSED"
        elif target_enum == VerificationState.RESOLUTION_DISPUTED:
            case.status = "MONITORING"
        elif target_enum == VerificationState.AWAITING_VERIFICATION and case.status == "CLOSED":
            case.status = "OPEN"

        if db:
            db.add(case)
            db.commit()
            db.refresh(case)

            record_event(
                db=db,
                case_id=case.id,
                event_type="VERIFICATION_STATE_CHANGED",
                origin=origin,
                actor=actor,
                source="VerificationStateMachine",
                payload={
                    "old_state": old_state,
                    "new_state": target_enum.value,
                    "case_status": case.status,
                    "reason": reason,
                },
            )

        return case
