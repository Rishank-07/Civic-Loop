"""
CivicLoop Background Worker Service
Processes tasks table with idempotency, exponential retry backoff,
crash recovery (lease timeouts), and auditable execution.
"""

import time
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, setup_database_triggers
from backend.app.core.config import settings
from backend.app.models.task import Task
from backend.app.domain.task_service import execute_task, recover_stuck_tasks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


def execute_single_task(task: Task, db: Session) -> bool:
    return execute_task(task, db)


def process_pending_tasks(db: Session, limit: int = 10) -> int:
    """
    Recovers any stuck tasks, then queries and executes pending tasks.
    """
    # 1. Crash recovery for tasks stuck in RUNNING
    recover_stuck_tasks(db, lease_timeout_minutes=5)

    # 2. Query pending tasks ready to run
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
