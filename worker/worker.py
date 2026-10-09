"""
CivicLoop Background Worker Service
Shares backend models and database session.
Processes tasks table with idempotency, exponential retry backoff,
and auditable execution.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, setup_database_triggers
from backend.app.core.config import settings
from backend.app.models.task import Task
from backend.app.domain.timeline_service import record_event, TimelineOrigin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


def execute_single_task(task: Task, db: Session) -> bool:
    """
    Executes a specific task with retry and idempotency semantics.
    Returns True if completed successfully, False otherwise.
    """
    task.status = "RUNNING"
    task.attempts += 1
    db.commit()

    logger.info(f"Executing task {task.id} (type: {task.task_type}, attempt {task.attempts}/{task.max_attempts})")

    try:
        if task.task_type == "SYNC_EXTERNAL_STATUS":
            # Simulate syncing with public civic portal (e.g. BBMP Sahaaya or Mock)
            if task.case_id:
                record_event(
                    db=db,
                    case_id=task.case_id,
                    event_type="TASK_COMPLETED_EXTERNAL_SYNC",
                    origin=TimelineOrigin.SYSTEM_EVENT,
                    actor="CivicLoop Worker",
                    source="Task Worker Engine",
                    payload={"task_id": task.id, "status": "SYNCED_NO_CHANGE"},
                )
        elif task.task_type == "AUDIT_VERIFICATION_DISPUTE":
            if task.case_id:
                record_event(
                    db=db,
                    case_id=task.case_id,
                    event_type="DISPUTE_AUDITED",
                    origin=TimelineOrigin.SYSTEM_EVENT,
                    actor="CivicLoop Worker",
                    source="Dispute Engine",
                    payload={"task_id": task.id, "audit_result": "DISPUTE_ACTIVE"},
                )
        elif task.task_type == "FAIL_TEST_TASK":
            raise RuntimeError("Deliberate failure for retry testing")
        else:
            logger.info(f"Generic task type {task.task_type} acknowledged.")

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
            logger.error(f"Task {task.id} permanently failed after {task.attempts} attempts: {exc}")
        else:
            task.status = "PENDING"
            # Exponential backoff retry
            backoff_seconds = (2 ** task.attempts) * 5
            task.run_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            logger.warning(f"Task {task.id} failed, retrying in {backoff_seconds}s: {exc}")

        db.commit()
        return False


def process_pending_tasks(db: Session, limit: int = 10) -> int:
    """
    Scans for and executes up to `limit` pending tasks ready to run.
    Returns the number of tasks processed.
    """
    now = datetime.now(timezone.utc)
    tasks = (
        db.query(Task)
        .filter(Task.status == "PENDING", Task.run_at <= now)
        .order_by(Task.run_at.asc())
        .limit(limit)
        .all()
    )

    processed = 0
    for task in tasks:
        execute_single_task(task, db)
        processed += 1

    return processed


def run_worker_loop():
    logger.info("Starting CivicLoop background task worker...")
    setup_database_triggers()

    while True:
        try:
            with SessionLocal() as db:
                count = process_pending_tasks(db)
                if count > 0:
                    logger.info(f"Processed {count} task(s).")
        except Exception as e:
            logger.error(f"Worker iteration error: {e}")

        time.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_worker_loop()
