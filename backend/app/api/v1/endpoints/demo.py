"""
CivicLoop Demo Control Endpoint (Dev / Demo Harness)
Allows fast-forwarding scheduled worker tasks and triggering simulated official closures
so that the entire multi-day civic lifecycle can be experienced in under 2 minutes.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.case import Case
from backend.app.models.task import Task
from backend.app.models.complaint import ComplaintRecord
from backend.app.connectors.mock_connector import MockPortalConnector
from backend.app.domain.task_service import execute_task, schedule_task

router = APIRouter()


@router.post("/fast-forward")
def fast_forward_tasks(
    seconds: int = 86400,  # 1 day by default
    run_now: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fast-forwards time for all pending tasks by subtracting `seconds` from `run_at`.
    Optionally triggers immediate execution.
    """
    pending_tasks = db.query(Task).filter(Task.status == "PENDING").all()
    now = datetime.now(timezone.utc)

    for t in pending_tasks:
        t.run_at = t.run_at - timedelta(seconds=seconds)

    db.commit()

    executed_count = 0
    if run_now:
        ready_tasks = db.query(Task).filter(Task.status == "PENDING", Task.run_at <= now).all()
        for t in ready_tasks:
            if execute_task(t, db):
                executed_count += 1

    return {
        "status": "fast_forward_complete",
        "advanced_seconds": seconds,
        "tasks_advanced": len(pending_tasks),
        "tasks_executed": executed_count,
    }


@router.post("/cases/{case_id}/simulate-closure")
def simulate_case_closure(
    case_id: int,
    closure_status: str = "RESOLVED",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulates receipt of an official closure from BBMP Sahaaya / Swachhata portal for the case.
    Schedules and executes a SYNC_EXTERNAL_STATUS task immediately.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    complaints = db.query(ComplaintRecord).filter(ComplaintRecord.case_id == case_id).all()
    if not complaints:
        raise HTTPException(status_code=400, detail="Case has no complaint records to simulate closure on.")

    # Configure Mock Portal to return simulated closure
    for c in complaints:
        MockPortalConnector.set_mock_status(c.external_id or str(c.id), closure_status)
        MockPortalConnector.set_mock_status(c.source, closure_status)
    MockPortalConnector.set_mock_status("DEFAULT", closure_status)

    # Schedule sync task and execute immediately
    bucket = int(datetime.now(timezone.utc).timestamp())
    task = schedule_task(
        db=db,
        task_type="SYNC_EXTERNAL_STATUS",
        idempotency_key=f"demo-sync-{case.id}-{bucket}",
        case_id=case.id,
        delay_seconds=0,
    )

    success = execute_task(task, db)
    db.refresh(case)

    return {
        "status": "simulated_closure_dispatched",
        "case_id": case.id,
        "case_verification_state": case.verification_state,
        "task_id": task.id,
        "execution_success": success,
        "message": f"Mock portal reported '{closure_status}'. Case moved to AWAITING_VERIFICATION and citizen prompted.",
    }


@router.post("/set-mock-unavailable")
def set_mock_portal_unavailable(
    unavailable: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Configures the mock connector to simulate portal downtime (HTTP 503 / timeout)."""
    MockPortalConnector.set_unavailable(unavailable)
    return {"status": "mock_portal_configured", "unavailable": unavailable}


@router.post("/reset-mock-portal")
def reset_mock_portal(
    current_user: User = Depends(get_current_user),
):
    MockPortalConnector.reset()
    return {"status": "mock_portal_reset"}
