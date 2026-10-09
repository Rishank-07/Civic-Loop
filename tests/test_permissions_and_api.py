import pytest
from backend.app.models.case import Case
from backend.app.models.task import Task
from backend.app.domain.timeline_service import record_event, TimelineOrigin
from worker.worker import execute_single_task


def test_auth_login_success(client, test_users):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "citizen1@example.com", "password": "Secret123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["email"] == "citizen1@example.com"
    assert data["role"] == "CITIZEN"


def test_auth_login_invalid_password(client, test_users):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "citizen1@example.com", "password": "WrongPassword"},
    )
    assert response.status_code == 401


def test_create_case_and_timeline_event(client, user1_token):
    headers = {"Authorization": f"Bearer {user1_token}"}
    payload = {
        "title": "Severe Drain Clogging near Indiranagar Metro",
        "issue_category": "DRAINAGE",
        "location_text": "CMH Road, Indiranagar, Bengaluru",
        "lat": 12.9784,
        "lng": 77.6408,
        "ward": "Ward 80",
        "jurisdiction": "BBMP East",
        "initial_complaint_raw_text": "Monsoon water cannot flow into culvert due to plastic waste.",
        "initial_complaint_source": "BBMP Sahaaya",
    }
    response = client.post("/api/v1/cases", json=payload, headers=headers)
    assert response.status_code == 201
    case_data = response.json()
    case_id = case_data["id"]

    # Verify timeline was auto-populated
    timeline_res = client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)
    assert timeline_res.status_code == 200
    events = timeline_res.json()
    assert len(events) >= 2  # CASE_CREATED (SYSTEM_EVENT) and COMPLAINT_RECORDED (USER_CLAIM)
    event_types = [e["event_type"] for e in events]
    assert "CASE_CREATED" in event_types
    assert "COMPLAINT_RECORDED" in event_types


def test_permissions_citizen_isolation(client, db, test_users, user1_token, user2_token, officer_token):
    # Create case belonging to citizen1
    case = Case(
        user_id=test_users["user1"].id,
        title="Citizen One Private Case",
        issue_category="GARBAGE",
        location_text="Somewhere in Ward 150",
        ward="Ward 150",
        jurisdiction="BBMP Mahadevapura",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Citizen 1 accesses their own case -> OK
    res1 = client.get(
        f"/api/v1/cases/{case.id}",
        headers={"Authorization": f"Bearer {user1_token}"},
    )
    assert res1.status_code == 200

    # Citizen 2 attempts to access citizen 1's case -> 403 Forbidden
    res2 = client.get(
        f"/api/v1/cases/{case.id}",
        headers={"Authorization": f"Bearer {user2_token}"},
    )
    assert res2.status_code == 403

    # BBMP Officer accesses citizen 1's case -> 200 OK
    res_officer = client.get(
        f"/api/v1/cases/{case.id}",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert res_officer.status_code == 200


def test_timeline_read_endpoint_origin_filtering(client, db, test_users, user1_token):
    headers = {"Authorization": f"Bearer {user1_token}"}
    case = Case(
        user_id=test_users["user1"].id,
        title="Timeline Filter Test",
        issue_category="GARBAGE",
        location_text="Domlur 2nd Stage",
        ward="Ward 112",
        jurisdiction="BBMP East",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    record_event(db, case.id, "STATUS_UPDATE", TimelineOrigin.SOURCE_FACT, "BBMP Connector", "Sahaaya")
    record_event(db, case.id, "DISPUTE_CLAIM", TimelineOrigin.USER_CLAIM, "Citizen One", "Portal")
    record_event(db, case.id, "REASONING_STEP", TimelineOrigin.AI_RECOMMENDATION, "CivicLoop Agent", "Reasoner")

    # Filter by SOURCE_FACT
    res_fact = client.get(f"/api/v1/cases/{case.id}/timeline?origin=SOURCE_FACT", headers=headers)
    assert res_fact.status_code == 200
    events_fact = res_fact.json()
    assert len(events_fact) == 1
    assert events_fact[0]["origin"] == "SOURCE_FACT"

    # Filter by USER_CLAIM
    res_claim = client.get(f"/api/v1/cases/{case.id}/timeline?origin=USER_CLAIM", headers=headers)
    assert res_claim.status_code == 200
    events_claim = res_claim.json()
    assert len(events_claim) == 1
    assert events_claim[0]["origin"] == "USER_CLAIM"

    # Invalid origin filter
    res_invalid = client.get(f"/api/v1/cases/{case.id}/timeline?origin=INVALID_ORIGIN", headers=headers)
    assert res_invalid.status_code == 400


def test_api_verification_transition_validation(client, db, test_users, user1_token):
    headers = {"Authorization": f"Bearer {user1_token}"}
    case = Case(
        user_id=test_users["user1"].id,
        title="Verification API Test",
        issue_category="GARBAGE",
        location_text="HSR Layout",
        ward="Ward 174",
        jurisdiction="BBMP Bommanahalli",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Valid transition to RESOLUTION_DISPUTED
    res_valid = client.post(
        f"/api/v1/cases/{case.id}/transition-verification",
        json={
            "target_state": "RESOLUTION_DISPUTED",
            "reason": "Garbage was only moved 10 meters away rather than collected.",
        },
        headers=headers,
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["verification_state"] == "RESOLUTION_DISPUTED"

    # Invalid transition directly from RESOLUTION_DISPUTED to INSUFFICIENT_EVIDENCE
    res_invalid = client.post(
        f"/api/v1/cases/{case.id}/transition-verification",
        json={
            "target_state": "INSUFFICIENT_EVIDENCE",
            "reason": "Trying illegal transition directly from disputed to insufficient",
        },
        headers=headers,
    )
    assert res_invalid.status_code == 400
    data = res_invalid.json()
    assert "detail" in data
    assert data["detail"]["error"] == "InvalidStateTransitionError"


def test_task_worker_retry_and_idempotency(db, test_users):
    case = Case(
        user_id=test_users["user1"].id,
        title="Worker Test Case",
        issue_category="GARBAGE",
        location_text="Bellandur",
        ward="Ward 150",
        jurisdiction="BBMP Mahadevapura",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # 1. Success task execution
    task_ok = Task(
        case_id=case.id,
        task_type="SYNC_EXTERNAL_STATUS",
        status="PENDING",
        max_attempts=3,
        idempotency_key="unique_key_001",
    )
    db.add(task_ok)
    db.commit()

    success = execute_single_task(task_ok, db)
    assert success is True
    assert task_ok.status == "SUCCEEDED"
    assert task_ok.attempts == 1

    # 2. Failure and retry task
    task_fail = Task(
        case_id=case.id,
        task_type="FAIL_TEST_TASK",
        status="PENDING",
        max_attempts=2,
        idempotency_key="unique_key_002",
    )
    db.add(task_fail)
    db.commit()

    # Attempt 1 -> fails, remains PENDING for retry
    res1 = execute_single_task(task_fail, db)
    assert res1 is False
    assert task_fail.status == "PENDING"
    assert task_fail.attempts == 1

    # Attempt 2 -> fails, reaches max_attempts, becomes FAILED
    res2 = execute_single_task(task_fail, db)
    assert res2 is False
    assert task_fail.status == "FAILED"
    assert task_fail.attempts == 2
    assert "Deliberate failure" in task_fail.last_error
