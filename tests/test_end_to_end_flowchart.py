import io
import pytest
from PIL import Image
from backend.app.domain.knowledge_service import ingest_knowledge_seed
from backend.app.connectors.mock_connector import MockPortalConnector


@pytest.mark.asyncio
async def test_complete_end_to_end_flowchart_scenario(client, user1_token, test_users, db):
    """
    Authoritative End-to-End Scenario:
    1. Create case with initial complaint.
    2. Link suggestion identified and proposed.
    3. Agent recommends responsible department with verified statutory citations.
    4. Schedule automated follow-up monitoring task.
    5. Mock administrative closure arrives -> Case moves to AWAITING_VERIFICATION & citizen prompted.
    6. Citizen disputes outcome by uploading photo evidence.
    7. Timeline captures the entire auditable lifecycle with typed origins.
    """
    headers = {"Authorization": f"Bearer {user1_token}"}

    # 0. Ensure knowledge seed is ingested
    await ingest_knowledge_seed(db, force_reload=True)

    # -----------------------------------------------------------------
    # STEP 1: Create Case
    # -----------------------------------------------------------------
    case_create_payload = {
        "title": "Uncollected Solid Waste Blackspot",
        "issue_category": "GARBAGE",
        "location_text": "12th Main Road, Indiranagar",
        "lat": 12.9716,
        "lng": 77.5946,
        "ward": "Ward 112 (Domlur / Indiranagar)",
        "jurisdiction": "BBMP East Zone",
        "initial_complaint_raw_text": "Garbage has not been collected for 3 days near 12th Main Indiranagar.",
        "initial_complaint_source": "BBMP Sahaaya 2.0",
        "initial_external_id": "BBMP-SWM-IND-101",
    }
    res_case = client.post("/api/v1/cases", json=case_create_payload, headers=headers)
    assert res_case.status_code == 201
    case_data = res_case.json()
    case_id = case_data["id"]
    assert case_data["status"] == "OPEN"
    assert case_data["verification_state"] == "AWAITING_VERIFICATION"

    # -----------------------------------------------------------------
    # STEP 2: Find & Evaluate Case Link Suggestions
    # -----------------------------------------------------------------
    find_links_payload = {
        "category": case_data["issue_category"],
        "location_text": case_data["location_text"],
        "lat": case_data["lat"],
        "lng": case_data["lng"],
        "ward": case_data["ward"],
    }
    res_links = client.post("/api/v1/case-linking/find-links", json=find_links_payload, headers=headers)
    assert res_links.status_code == 200
    links_data = res_links.json()
    assert isinstance(links_data, list)

    # -----------------------------------------------------------------
    # STEP 3: Agent Recommends Department with Citations
    # -----------------------------------------------------------------
    res_agent_step = client.post(
        f"/api/v1/agent/cases/{case_id}/execute-tool",
        json={
            "tool_name": "lookup_department_responsibility",
            "arguments": {
                "query": "Solid waste garbage blackspot collectionIndiranagar",
                "ward": "Ward 112",
                "jurisdiction": "BBMP East",
            },
        },
        headers=headers,
    )
    assert res_agent_step.status_code == 200
    agent_res = res_agent_step.json()
    assert agent_res["action_type"] == "INFORMATION"
    result_data = agent_res["result"]
    assert len(result_data["citations"]) > 0
    assert "BBMP Solid Waste Management" in result_data["citations"][0]["department"]
    assert result_data["citations"][0]["source_url"] is not None

    # -----------------------------------------------------------------
    # STEP 4: Schedule Follow-Up Worker Task
    # -----------------------------------------------------------------
    res_followup = client.post(
        f"/api/v1/agent/cases/{case_id}/execute-tool",
        json={
            "tool_name": "schedule_followup",
            "arguments": {
                "case_id": case_id,
                "task_type": "SYNC_EXTERNAL_STATUS",
                "delay_seconds": 3600,
                "payload": {"portal": "BBMP Sahaaya 2.0"},
            },
        },
        headers=headers,
    )
    assert res_followup.status_code == 200
    followup_res = res_followup.json()
    assert followup_res["action_type"] == "FOLLOWUP_TASK"
    assert followup_res["result"]["status"] == "PENDING"

    # -----------------------------------------------------------------
    # STEP 5: Fast-forward Schedule & Simulate Official Closure
    # -----------------------------------------------------------------
    res_sim_closure = client.post(
        f"/api/v1/demo/cases/{case_id}/simulate-closure",
        params={"closure_status": "RESOLVED"},
        headers=headers,
    )
    assert res_sim_closure.status_code == 200
    closure_data = res_sim_closure.json()
    assert closure_data["execution_success"] is True

    # Verify notification received by citizen
    res_notifs = client.get("/api/v1/notifications", headers=headers)
    assert res_notifs.status_code == 200
    notifs = res_notifs.json()
    assert len(notifs) > 0
    assert any("Official Closure Received" in n["title"] for n in notifs)

    # -----------------------------------------------------------------
    # STEP 6: Citizen Disputes Outcome with Photo Evidence
    # -----------------------------------------------------------------
    # 6a. Upload Photo Evidence
    img = Image.new("RGB", (120, 120), color=(100, 150, 200))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    files = {"file": ("dispute_evidence.jpg", img_bytes, "image/jpeg")}
    data = {"provenance": "CITIZEN_CAMERA_UPLOAD"}

    res_upload = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files,
        data=data,
        headers=headers,
    )
    assert res_upload.status_code == 201
    evidence_item = res_upload.json()
    assert evidence_item["provenance"] == "CITIZEN_CAMERA_UPLOAD"
    assert "officially resolved" not in evidence_item["ai_description"].lower()

    # 6b. Citizen Transitions Verification State to RESOLUTION_DISPUTED
    res_transition = client.post(
        f"/api/v1/cases/{case_id}/transition-verification",
        json={
            "target_state": "RESOLUTION_DISPUTED",
            "reason": "Garbage has not been removed; photo submitted showing uncleared site.",
        },
        headers=headers,
    )
    assert res_transition.status_code == 200
    updated_case = res_transition.json()
    assert updated_case["verification_state"] == "RESOLUTION_DISPUTED"
    assert updated_case["status"] == "MONITORING"

    # -----------------------------------------------------------------
    # STEP 7: Audit Timeline Shows Everything With Typed Origins
    # -----------------------------------------------------------------
    res_timeline = client.get(f"/api/v1/cases/{case_id}/timeline", headers=headers)
    assert res_timeline.status_code == 200
    timeline = res_timeline.json()

    event_types = [e["event_type"] for e in timeline]
    origins = {e["origin"] for e in timeline}

    # Verify all stages recorded
    assert "CASE_CREATED" in event_types
    assert "COMPLAINT_RECORDED" in event_types
    assert "AI_DEPARTMENT_RECOMMENDATION" in event_types
    assert "TASK_SCHEDULED" in event_types
    assert "OFFICIAL_STATUS_UPDATED" in event_types
    assert "OUTCOME_VERIFICATION_REQUESTED" in event_types
    assert "EVIDENCE_SUBMITTED" in event_types
    assert "VERIFICATION_STATE_CHANGED" in event_types

    # Verify origin types
    assert "SOURCE_FACT" in origins
    assert "USER_CLAIM" in origins
    assert "AI_RECOMMENDATION" in origins
    assert "SYSTEM_EVENT" in origins
