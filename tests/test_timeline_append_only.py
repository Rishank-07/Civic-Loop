import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, InternalError
from backend.app.models.case import Case
from backend.app.models.timeline import TimelineEvent
from backend.app.domain.timeline_service import (
    record_event,
    TimelineOrigin,
    InvalidTimelineOriginError,
    CaseNotFoundError,
)


def test_record_event_success(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Timeline Test Case",
        issue_category="GARBAGE",
        location_text="Koramangala 4th Block",
        ward="Ward 151",
        jurisdiction="BBMP South",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Record SOURCE_FACT
    event1 = record_event(
        db=db,
        case_id=case.id,
        event_type="COMPLAINT_REGISTERED",
        origin=TimelineOrigin.SOURCE_FACT,
        actor="BBMP Sahaaya",
        source="External Gateway",
        payload={"ticket": "BLR-1234"},
    )
    assert event1.id is not None
    assert event1.origin == "SOURCE_FACT"
    assert event1.event_type == "COMPLAINT_REGISTERED"

    # Record AI_RECOMMENDATION
    event2 = record_event(
        db=db,
        case_id=case.id,
        event_type="AI_ESCALATION_PROPOSED",
        origin=TimelineOrigin.AI_RECOMMENDATION,
        actor="CivicLoop Agent",
        source="SOP Knowledge Base",
        payload={"recommended_sla_hours": 24},
    )
    assert event2.id is not None
    assert event2.origin == "AI_RECOMMENDATION"


def test_record_event_invalid_origin(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Invalid Origin Case",
        issue_category="DRAINAGE",
        location_text="BTM Layout",
        ward="Ward 176",
        jurisdiction="BBMP Bommanahalli",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    with pytest.raises(InvalidTimelineOriginError):
        record_event(
            db=db,
            case_id=case.id,
            event_type="ILLEGAL_EVENT",
            origin="UNKNOWN_PROVENANCE",
            actor="Bad Actor",
            source="Nowhere",
        )


def test_record_event_missing_case(db):
    with pytest.raises(CaseNotFoundError):
        record_event(
            db=db,
            case_id=999999,
            event_type="ORPHAN_EVENT",
            origin=TimelineOrigin.SYSTEM_EVENT,
            actor="System",
            source="Automated Cron",
        )


def test_database_trigger_blocks_update(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Trigger Test Case",
        issue_category="GARBAGE",
        location_text="HSR Sector 1",
        ward="Ward 174",
        jurisdiction="BBMP Bommanahalli",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    event = record_event(
        db=db,
        case_id=case.id,
        event_type="INITIAL_NOTE",
        origin=TimelineOrigin.SYSTEM_EVENT,
        actor="System",
        source="System",
    )

    # Attempt direct SQL UPDATE on timeline_events table
    with pytest.raises((IntegrityError, OperationalError, InternalError)) as exc_info:
        db.execute(
            text("UPDATE timeline_events SET actor = 'Malicious Update' WHERE id = :id"),
            {"id": event.id},
        )
        db.commit()

    assert "append-only" in str(exc_info.value).lower()
    db.rollback()


def test_database_trigger_blocks_delete(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Trigger Delete Test Case",
        issue_category="DRAINAGE",
        location_text="Bellandur ORR",
        ward="Ward 150",
        jurisdiction="BBMP Mahadevapura",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    event = record_event(
        db=db,
        case_id=case.id,
        event_type="AUDIT_LOG",
        origin=TimelineOrigin.SYSTEM_EVENT,
        actor="System",
        source="System",
    )

    # Attempt direct SQL DELETE on timeline_events table
    with pytest.raises((IntegrityError, OperationalError, InternalError)) as exc_info:
        db.execute(
            text("DELETE FROM timeline_events WHERE id = :id"),
            {"id": event.id},
        )
        db.commit()

    assert "append-only" in str(exc_info.value).lower()
    db.rollback()
