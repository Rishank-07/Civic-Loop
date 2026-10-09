import pytest
from backend.app.models.case import Case
from backend.app.domain.state_machine import (
    VerificationStateMachine,
    VerificationState,
    InvalidStateTransitionError,
)
from backend.app.domain.timeline_service import TimelineOrigin


def test_allowed_transitions():
    assert VerificationStateMachine.can_transition(
        VerificationState.AWAITING_VERIFICATION,
        VerificationState.CITIZEN_CONFIRMED_RESOLVED,
    )
    assert VerificationStateMachine.can_transition(
        VerificationState.AWAITING_VERIFICATION,
        VerificationState.RESOLUTION_DISPUTED,
    )
    assert VerificationStateMachine.can_transition(
        VerificationState.AWAITING_VERIFICATION,
        VerificationState.INSUFFICIENT_EVIDENCE,
    )
    assert VerificationStateMachine.can_transition(
        VerificationState.RESOLUTION_DISPUTED,
        VerificationState.AWAITING_VERIFICATION,
    )
    assert VerificationStateMachine.can_transition(
        VerificationState.CITIZEN_CONFIRMED_RESOLVED,
        VerificationState.RESOLUTION_DISPUTED,
    )


def test_disallowed_transitions():
    # DISPUTED to INSUFFICIENT_EVIDENCE is not directly allowed
    assert not VerificationStateMachine.can_transition(
        VerificationState.RESOLUTION_DISPUTED,
        VerificationState.INSUFFICIENT_EVIDENCE,
    )
    # Self transitions
    assert not VerificationStateMachine.can_transition(
        VerificationState.CITIZEN_CONFIRMED_RESOLVED,
        VerificationState.CITIZEN_CONFIRMED_RESOLVED,
    )


def test_transition_execution(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Test Garbage Pile",
        issue_category="GARBAGE",
        location_text="12th Main Road, Indiranagar",
        ward="Ward 80",
        jurisdiction="BBMP East",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Valid transition to RESOLUTION_DISPUTED
    updated_case = VerificationStateMachine.transition(
        case=case,
        new_state=VerificationState.RESOLUTION_DISPUTED,
        reason="Field inspection proved contractor did not clear garbage",
        actor="Citizen One",
        origin=TimelineOrigin.USER_CLAIM,
        db=db,
    )

    assert updated_case.verification_state == "RESOLUTION_DISPUTED"
    assert updated_case.status == "MONITORING"

    # Valid transition to CITIZEN_CONFIRMED_RESOLVED
    updated_case = VerificationStateMachine.transition(
        case=case,
        new_state=VerificationState.CITIZEN_CONFIRMED_RESOLVED,
        reason="Contractor revisited and fully cleared blackspot",
        actor="Citizen One",
        origin=TimelineOrigin.USER_CLAIM,
        db=db,
    )

    assert updated_case.verification_state == "CITIZEN_CONFIRMED_RESOLVED"
    assert updated_case.status == "CLOSED"


def test_invalid_transition_raises_typed_error(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Test SWD Blockage",
        issue_category="DRAINAGE",
        location_text="Intermediate Ring Road",
        ward="Ward 112",
        jurisdiction="BBMP East",
        status="CLOSED",
        verification_state="CITIZEN_CONFIRMED_RESOLVED",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        VerificationStateMachine.transition(
            case=case,
            new_state=VerificationState.INSUFFICIENT_EVIDENCE,
            reason="Invalid transition directly from RESOLVED to INSUFFICIENT",
            actor="System",
            origin=TimelineOrigin.SYSTEM_EVENT,
            db=db,
        )

    assert exc_info.value.from_state == "CITIZEN_CONFIRMED_RESOLVED"
    assert exc_info.value.to_state == "INSUFFICIENT_EVIDENCE"
    assert "RESOLUTION_DISPUTED" in exc_info.value.allowed
