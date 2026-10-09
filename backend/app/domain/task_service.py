"""
CivicLoop Task Execution Engine & Crash Recovery Service (Feature 4)
Handles task persistence with idempotency keys, bounded retries with exponential backoff,
lease timeout crash recovery, and connector status evaluations.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from backend.app.models.task import Task
from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.connectors.mock_connector import MockPortalConnector
from backend.app.connectors.manual_connector import ManualUpdateConnector
from backend.app.connectors.base import StatusOutcome, StatusResult
from backend.app.domain.timeline_service import record_event, TimelineOrigin
from backend.app.domain.state_machine import VerificationStateMachine, VerificationState
from backend.app.domain.notification_service import send_notification

logger = logging.getLogger(__name__)

LEASE_TIMEOUT_MINUTES = 5


def recover_stuck_tasks(db: Session, lease_timeout_minutes: int = LEASE_TIMEOUT_MINUTES) -> int:
    """
    Crash recovery: Re-queues tasks stuck in 'RUNNING' status longer than lease_timeout_minutes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=lease_timeout_minutes)
    stuck_tasks = (
        db.query(Task)
        .filter(Task.status == "RUNNING", Task.locked_at <= cutoff)
        .all()
    )

    count = 0
    for task in stuck_tasks:
        logger.warning(f"Recovering stuck task {task.id} (locked at {task.locked_at}). Re-queuing.")
        task.status = "PENDING"
        task.locked_at = None
        count += 1

    if count > 0:
        db.commit()
    return count


def schedule_task(
    db: Session,
    task_type: str,
    idempotency_key: str,
    case_id: Optional[int] = None,
    delay_seconds: int = 0,
    payload: Optional[Dict[str, Any]] = None,
    max_attempts: int = 3,
) -> Task:
    """
    Schedules a new background task. Enforces idempotency via idempotency_key.
    """
    existing = db.query(Task).filter(Task.idempotency_key == idempotency_key).first()
    if existing:
        logger.info(f"Task with idempotency key '{idempotency_key}' already exists (ID: {existing.id}, status: {existing.status}).")
        return existing

    run_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    task = Task(
        case_id=case_id,
        task_type=task_type,
        status="PENDING",
        run_at=run_at,
        attempts=0,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key,
        payload_json=payload or {},
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    if case_id:
        record_event(
            db=db,
            case_id=case_id,
            event_type="TASK_SCHEDULED",
            origin=TimelineOrigin.SYSTEM_EVENT,
            actor="Task Scheduler",
            source="Worker Engine",
            payload={
                "task_id": task.id,
                "task_type": task_type,
                "run_at": run_at.isoformat(),
                "idempotency_key": idempotency_key,
            },
        )

    return task


def execute_task(task: Task, db: Session) -> bool:
    """
    Executes a single task with lease locking, bounded retries, and connector integration.
    """
    now = datetime.now(timezone.utc)
    task.status = "RUNNING"
    task.locked_at = now
    task.attempts += 1
    db.commit()

    logger.info(f"Executing task {task.id} ({task.task_type}, attempt {task.attempts}/{task.max_attempts})")

    try:
        if task.task_type == "SYNC_EXTERNAL_STATUS":
            _handle_sync_external_status(task, db)
        elif task.task_type == "SEND_REMINDER":
            _handle_send_reminder(task, db)
        elif task.task_type == "FAIL_TEST_TASK":
            raise RuntimeError("Deliberate failure for retry testing")
        else:
            logger.info(f"Custom task type '{task.task_type}' executed.")

        task.status = "SUCCEEDED"
        task.last_error = None
        db.commit()
        logger.info(f"Task {task.id} succeeded.")
        return True

    except Exception as exc:
        db.rollback()
        task.last_error = str(exc)
        if task.attempts >= task.max_attempts:
            task.status = "FAILED"
            logger.error(f"Task {task.id} permanently FAILED after {task.attempts} attempts: {exc}")
            if task.case_id:
                record_event(
                    db=db,
                    case_id=task.case_id,
                    event_type="TASK_FAILED_PERMANENTLY",
                    origin=TimelineOrigin.SYSTEM_EVENT,
                    actor="CivicLoop Worker",
                    source="Worker Engine",
                    payload={"task_id": task.id, "error": str(exc), "attempts": task.attempts},
                )
        else:
            task.status = "PENDING"
            backoff_seconds = (2 ** task.attempts) * 5
            task.run_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            logger.warning(f"Task {task.id} failed, retry scheduled in {backoff_seconds}s: {exc}")

        db.commit()
        return False


def _handle_sync_external_status(task: Task, db: Session):
    case_id = task.case_id
    if not case_id:
        return

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return

    complaints = db.query(ComplaintRecord).filter(ComplaintRecord.case_id == case_id).all()
    if not complaints:
        return

    mock_connector = MockPortalConnector()

    for record in complaints:
        status_res = mock_connector.check_status(record)

        if status_res.outcome == StatusOutcome.UNAVAILABLE:
            # Rule: UNAVAILABLE is recorded as "unable to verify", never as "unchanged"
            record_event(
                db=db,
                case_id=case.id,
                event_type="STATUS_CHECK_UNAVAILABLE",
                origin=TimelineOrigin.SOURCE_FACT,
                actor="Worker Connector",
                source=status_res.source_label,
                payload={
                    "complaint_id": record.id,
                    "external_id": record.external_id,
                    "verification_result": "unable to verify",
                    "note": status_res.message,
                },
            )
            continue

        if status_res.outcome == StatusOutcome.OK:
            old_official = record.official_status
            record.official_status = status_res.external_status
            record.official_status_retrieved_at = datetime.now(timezone.utc)
            db.commit()

            record_event(
                db=db,
                case_id=case.id,
                event_type="OFFICIAL_STATUS_UPDATED",
                origin=TimelineOrigin.SOURCE_FACT,
                actor="Portal Connector",
                source=status_res.source_label,
                payload={
                    "complaint_id": record.id,
                    "external_id": record.external_id,
                    "old_status": old_official,
                    "new_official_status": status_res.external_status,
                    "is_closure": status_res.is_closure,
                    "raw_payload": status_res.raw_payload,
                },
            )

            if status_res.is_closure:
                # If administrative closure received:
                # 1. Move case to AWAITING_VERIFICATION (if not already verified)
                if case.verification_state != VerificationState.CITIZEN_CONFIRMED_RESOLVED.value:
                    case.verification_state = VerificationState.AWAITING_VERIFICATION.value
                    db.commit()

                # 2. Ask citizen outcome verification
                send_notification(
                    db=db,
                    user_id=case.user_id,
                    case_id=case.id,
                    title="Official Closure Received: Please Verify",
                    message=(
                        f"BBMP/Municipal portal marked complaint #{record.external_id or record.id} as '{status_res.external_status}'. "
                        "Please inspect the site and confirm whether the issue is actually resolved or if you wish to dispute it."
                    ),
                )

                record_event(
                    db=db,
                    case_id=case.id,
                    event_type="OUTCOME_VERIFICATION_REQUESTED",
                    origin=TimelineOrigin.SYSTEM_EVENT,
                    actor="CivicLoop System",
                    source="Closure Detection Engine",
                    payload={
                        "complaint_id": record.id,
                        "official_status": status_res.external_status,
                        "notification_sent": True,
                    },
                )


def _handle_send_reminder(task: Task, db: Session):
    case_id = task.case_id
    if not case_id:
        return
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return

    payload = task.payload_json or {}
    message = payload.get("message", f"Reminder regarding Case #{case.id}: {case.title}")
    
    send_notification(
        db=db,
        user_id=case.user_id,
        case_id=case.id,
        title="CivicLoop Follow-up Reminder",
        message=message,
    )

    record_event(
        db=db,
        case_id=case.id,
        event_type="REMINDER_DISPATCHED",
        origin=TimelineOrigin.SYSTEM_EVENT,
        actor="Worker Notification Engine",
        source="Reminder Service",
        payload={"task_id": task.id, "recipient_user_id": case.user_id},
    )
