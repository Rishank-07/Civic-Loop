import pytest
from backend.app.models.case import Case
from backend.app.models.user import User
from backend.app.models.timeline import TimelineEvent
from backend.app.agent.tools import TOOL_REGISTRY, get_all_tool_schemas
from backend.app.agent.policy import AgentPolicyLayer, PolicyViolationError
from backend.app.agent.executor import execute_agent_tool, decide_approval
from backend.app.domain.knowledge_service import ingest_knowledge_seed, retrieve_knowledge


@pytest.mark.asyncio
async def test_tool_registry_schemas_and_metadata():
    schemas = get_all_tool_schemas()
    assert len(schemas) == 11
    
    # Verify tool names
    expected_tools = {
        "classify_issue",
        "lookup_department_responsibility",
        "retrieve_guidance",
        "request_clarification",
        "draft_grievance",
        "draft_referral",
        "schedule_followup",
        "check_source_status",
        "request_citizen_verification",
        "record_event",
        "summarise_timeline",
    }
    registered_names = set(TOOL_REGISTRY.keys())
    assert expected_tools.issubset(registered_names)

    # Verify external flags
    assert TOOL_REGISTRY["draft_grievance"].external is True
    assert TOOL_REGISTRY["draft_referral"].external is True
    assert TOOL_REGISTRY["lookup_department_responsibility"].external is False


@pytest.mark.asyncio
async def test_policy_layer_rejects_unauthorized_role(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Overflowing Drain",
        issue_category="DRAINAGE",
        location_text="Koramangala 4th Block",
        ward="Ward 151",
        jurisdiction="BBMP South",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # draft_referral requires OFFICER role; citizen calling it should be rejected
    is_valid, reason = AgentPolicyLayer.validate_action(
        tool_name="draft_referral",
        arguments={"case_id": case.id, "from_department": "BBMP", "to_department": "BWSSB", "reason": "Culvert cross-flow"},
        case=case,
        user=citizen,
        db=db,
    )
    assert is_valid is False
    assert "lacks permission" in reason

    # Verify policy rejection was recorded as a SYSTEM_EVENT in the timeline
    rejection_event = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case.id, TimelineEvent.event_type == "POLICY_REJECTION")
        .first()
    )
    assert rejection_event is not None
    assert rejection_event.origin == "SYSTEM_EVENT"
    assert rejection_event.payload_json["attempted_tool"] == "draft_referral"


@pytest.mark.asyncio
async def test_approval_gating_for_external_action(db, test_users):
    citizen = test_users["user1"]
    case = Case(
        user_id=citizen.id,
        title="Uncollected Commercial Waste",
        issue_category="GARBAGE",
        location_text="Indiranagar 100ft Road",
        ward="Ward 112",
        jurisdiction="BBMP East",
        status="OPEN",
        verification_state="AWAITING_VERIFICATION",
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # Calling draft_grievance creates a pending approval without executing outward mutation
    res = await execute_agent_tool(
        tool_name="draft_grievance",
        arguments={
            "case_id": case.id,
            "target_department": "BBMP SWM",
            "portal_name": "BBMP Sahaaya 2.0",
            "grievance_text": "Commercial garbage pile overflowing on 100ft road Indiranagar.",
        },
        case_id=case.id,
        user=citizen,
        db=db,
    )

    assert res["action_type"] == "EXTERNAL_ACTION"
    assert res["requires_approval"] is True
    assert res["status"] == "PENDING"
    approval_id = res["approval_id"]

    # User decides to APPROVE
    approval = decide_approval(approval_id=approval_id, decision="APPROVED", user=citizen, db=db)
    assert approval.status == "APPROVED"

    # Timeline event emitted with SOURCE_FACT
    dispatch_event = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case.id, TimelineEvent.event_type == "EXTERNAL_ACTION_DISPATCHED")
        .first()
    )
    assert dispatch_event is not None
    assert dispatch_event.origin == "SOURCE_FACT"


@pytest.mark.asyncio
async def test_knowledge_retrieval_and_citations(db):
    await ingest_knowledge_seed(db, force_reload=True)

    res = await retrieve_knowledge(db=db, query="Who is responsible for garbage blackspots and SWM?", top_k=2)
    assert res["is_sufficient"] is True
    assert len(res["results"]) > 0
    top = res["results"][0]
    assert "SWM" in top["department"] or "Solid Waste" in top["title"]
    assert top["source_url"] is not None
    assert top["last_verified"] is not None
