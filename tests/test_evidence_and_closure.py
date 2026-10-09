import pytest
import io
from PIL import Image
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.models.timeline import TimelineEvent
from backend.app.domain.evidence_service import save_and_process_evidence
from backend.app.domain.state_machine import VerificationStateMachine, VerificationState, InvalidStateTransitionError


@pytest.mark.asyncio
async def test_evidence_upload_neutral_vision_and_timeline(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Unrepaired Pothole",
        issue_category="OTHER",
        location_text="MG Road Junction",
        ward="Ward 111",
        jurisdiction="BBMP East",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Create dummy image in memory
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    evidence = await save_and_process_evidence(
        db=db,
        case_id=case.id,
        file_bytes=img_bytes,
        filename="pothole_field_photo.jpg",
        mime_type="image/jpeg",
        user=citizen,
    )

    assert evidence.id is not None
    assert "officially resolved" not in evidence.ai_description.lower()
    assert evidence.provenance == "CITIZEN_CAMERA_UPLOAD"

    # Timeline event
    event = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case.id, TimelineEvent.event_type == "EVIDENCE_SUBMITTED")
        .first()
    )
    assert event is not None
    assert event.origin == "USER_CLAIM"


def test_verification_state_transitions(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Garbage Pile",
        issue_category="GARBAGE",
        location_text="BTM 2nd Stage",
        ward="Ward 176",
        jurisdiction="BBMP South",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Citizen disputes resolution
    case = VerificationStateMachine.transition(
        case=case,
        new_state=VerificationState.RESOLUTION_DISPUTED,
        reason="Garbage is still present at the corner of 7th cross.",
        actor=citizen.name,
        db=db,
    )
    assert case.verification_state == "RESOLUTION_DISPUTED"
    assert case.status == "MONITORING"

    # Citizen later confirms resolved
    case = VerificationStateMachine.transition(
        case=case,
        new_state=VerificationState.CITIZEN_CONFIRMED_RESOLVED,
        reason="Sanitation crew cleared the blackspot.",
        actor=citizen.name,
        db=db,
    )
    assert case.verification_state == "CITIZEN_CONFIRMED_RESOLVED"
    assert case.status == "CLOSED"
