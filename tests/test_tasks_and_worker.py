from datetime import datetime, timezone, timedelta
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.models.task import Task
from backend.app.models.timeline import TimelineEvent
from backend.app.domain.task_service import (
    schedule_task,
    execute_task,
    recover_stuck_tasks,
)
from backend.app.connectors.mock_connector import MockPortalConnector


def test_duplicate_task_prevention(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Blocked Culvert",
        issue_category="DRAINAGE",
        location_text="HSR Layout Sector 1",
        ward="Ward 174",
        jurisdiction="BBMP South",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Schedule task with idempotency key
    task1 = schedule_task(
        db=db,
        task_type="SYNC_EXTERNAL_STATUS",
        idempotency_key="idemp-key-100",
        case_id=case.id,
    )
    # Schedule identical task with same idempotency key
    task2 = schedule_task(
        db=db,
        task_type="SYNC_EXTERNAL_STATUS",
        idempotency_key="idemp-key-100",
        case_id=case.id,
    )

    assert task1.id == task2.id
    total_tasks = db.query(Task).filter(Task.idempotency_key == "idemp-key-100").count()
    assert total_tasks == 1


def test_crash_recovery_stuck_running_tasks(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Open Manhole",
        issue_category="DRAINAGE",
        location_text="Domlur 2nd Stage",
        ward="Ward 112",
        jurisdiction="BBMP East",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Create task artificially stuck in RUNNING 10 minutes ago
    old_lock = datetime.now(timezone.utc) - timedelta(minutes=10)
    task = Task(
        case_id=case.id,
        task_type="SYNC_EXTERNAL_STATUS",
        status="RUNNING",
        run_at=old_lock,
        locked_at=old_lock,
        idempotency_key="stuck-task-key-1",
    )
    db.add(task)
    db.commit()

    recovered_count = recover_stuck_tasks(db, lease_timeout_minutes=5)
    assert recovered_count == 1

    db.refresh(task)
    assert task.status == "PENDING"
    assert task.locked_at is None


def test_source_unavailable_recorded_as_unable_to_verify(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Debris on Footpath",
        issue_category="OTHER",
        location_text="Whitefield Main Road",
        ward="Ward 84",
        jurisdiction="BBMP Mahadevapura",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    complaint = ComplaintRecord(
        case_id=case.id,
        source="BBMP Sahaaya 2.0",
        external_id="BBMP-998811",
        raw_text="Debris on footpath near bus stop",
        official_status="IN_PROGRESS",
        retrieval_method="MOCK",
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # Force mock connector unavailable (simulate network timeout / server 503)
    MockPortalConnector.set_unavailable(True)

    task = schedule_task(
        db=db,
        task_type="SYNC_EXTERNAL_STATUS",
        idempotency_key="sync-unavailable-test",
        case_id=case.id,
    )
    execute_task(task, db)

    MockPortalConnector.reset()

    # Verify timeline event recorded as "unable to verify" (never assumed unchanged)
    unavail_event = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case.id, TimelineEvent.event_type == "STATUS_CHECK_UNAVAILABLE")
        .first()
    )
    assert unavail_event is not None
    assert unavail_event.payload_json["verification_result"] == "unable to verify"


def test_retry_limits_and_exponential_backoff(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Test Case",
        issue_category="GARBAGE",
        location_text="Test Ward",
        ward="Ward 1",
        jurisdiction="BBMP",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()

    task = schedule_task(
        db=db,
        task_type="FAIL_TEST_TASK",
        idempotency_key="failing-task-1",
        case_id=case.id,
        max_attempts=2,
    )

    # Attempt 1: Should fail and back off to PENDING
    execute_task(task, db)
    db.refresh(task)
    assert task.status == "PENDING"
    assert task.attempts == 1

    # Attempt 2: Should hit max_attempts and become FAILED
    execute_task(task, db)
    db.refresh(task)
    assert task.status == "FAILED"
    assert task.attempts == 2
