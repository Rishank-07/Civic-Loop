"""
CivicLoop AI Agent Planner
Gathers comprehensive case context (records, timeline summary, verification state, knowledge retrieval),
and prompts the open-weight agent model to choose ONE next action via tool calling.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.complaint import ComplaintRecord
from backend.app.models.timeline import TimelineEvent
from backend.app.ai.llm import llm_client
from backend.app.agent.tools import TOOL_REGISTRY, get_all_tool_schemas
from backend.app.domain.knowledge_service import retrieve_knowledge

logger = logging.getLogger(__name__)


def build_case_context_summary(case: Case, db: Session) -> Dict[str, Any]:
    """Compiles all relevant context for the planner."""
    complaints = (
        db.query(ComplaintRecord)
        .filter(ComplaintRecord.case_id == case.id)
        .order_by(ComplaintRecord.created_at.asc())
        .all()
    )
    timeline = (
        db.query(TimelineEvent)
        .filter(TimelineEvent.case_id == case.id)
        .order_by(TimelineEvent.created_at.asc())
        .all()
    )

    records_summary = [
        {
            "id": c.id,
            "source": c.source,
            "external_id": c.external_id,
            "official_status": c.official_status,
            "retrieval_method": c.retrieval_method,
            "raw_text": c.raw_text[:200],
        }
        for c in complaints
    ]

    timeline_summary = [
        {
            "event_type": t.event_type,
            "origin": t.origin,
            "actor": t.actor,
            "source": t.source,
            "payload": t.payload_json,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in timeline[-10:]  # last 10 events
    ]

    return {
        "case_id": case.id,
        "title": case.title,
        "issue_category": case.issue_category,
        "location_text": case.location_text,
        "ward": case.ward,
        "jurisdiction": case.jurisdiction,
        "status": case.status,
        "verification_state": case.verification_state,
        "complaint_records": records_summary,
        "recent_timeline": timeline_summary,
    }


async def plan_next_action(
    case: Case,
    db: Session,
    user_goal: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Plans the single next action for a case using the open-weight agent model.
    """
    context = build_case_context_summary(case, db)
    
    # Retrieve relevant knowledge to ground the prompt
    query_text = f"{case.title} {case.issue_category} {case.location_text}"
    knowledge_results = await retrieve_knowledge(db=db, query=query_text, top_k=3)

    system_prompt = (
        "You are the CivicLoop Civic Intelligence Agent for Bengaluru.\n"
        "Your task is to review the case state and select EXACTLY ONE tool action to take next.\n"
        "Rules:\n"
        "1. Never guess or hallucinate department contacts or SLAs. Ground answers in verified knowledge citations.\n"
        "2. If an official closure was reported, trigger citizen outcome verification.\n"
        "3. For external actions (drafting portal grievances, transfers), call draft_grievance or draft_referral.\n"
        "4. If information is insufficient or missing required fields, call request_clarification.\n"
        "5. For jurisdictional advice, call lookup_department_responsibility or retrieve_guidance.\n"
        "6. For follow-up monitoring, call schedule_followup."
    )

    user_message = (
        f"Case Context:\n{json.dumps(context, indent=2)}\n\n"
        f"Verified Knowledge Chunks:\n{json.dumps(knowledge_results['results'], indent=2)}\n\n"
        f"User/System Directive: {user_goal or 'Determine the next appropriate step for this case according to the CivicLoop workflow.'}\n\n"
        "Choose ONE tool to call with appropriate parameters."
    )

    tools = get_all_tool_schemas()

    try:
        import asyncio
        response = await asyncio.wait_for(
            llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                tools=tools,
                temperature=0.1,
                purpose="agent_planner",
                timeout=1.0,
            ),
            timeout=1.0,
        )

        message = response.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            call = tool_calls[0]["function"]
            tool_name = call["name"]
            arguments = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
            return {
                "tool_name": tool_name,
                "arguments": arguments,
                "reasoning": message.get("content") or "Selected tool based on case context.",
                "knowledge_context": knowledge_results,
            }

        # If model answered in text with JSON or direct reasoning
        content = message.get("content", "")
        # Fallback heuristic mapping if tool_calls not directly structured by runner
        if "clarification" in content.lower() or not knowledge_results.get("is_sufficient"):
            return {
                "tool_name": "request_clarification",
                "arguments": {"question": "Could you provide more specific details or the exact street location?", "missing_fields": ["location_details"]},
                "reasoning": content,
                "knowledge_context": knowledge_results,
            }
        else:
            return {
                "tool_name": "lookup_department_responsibility",
                "arguments": {"query": case.title, "ward": case.ward, "jurisdiction": case.jurisdiction},
                "reasoning": content,
                "knowledge_context": knowledge_results,
            }

    except Exception as exc:
        logger.warning(f"Agent planner model call error ({exc}). Falling back to heuristic planning.")
        # Deterministic fallback based on flowchart state
        if case.verification_state == "AWAITING_VERIFICATION":
            return {
                "tool_name": "request_citizen_verification",
                "arguments": {
                    "case_id": case.id,
                    "message": "Official status was updated. Please inspect the site and confirm if the issue is resolved.",
                },
                "reasoning": "Case is awaiting citizen verification.",
                "knowledge_context": knowledge_results,
            }
        else:
            return {
                "tool_name": "lookup_department_responsibility",
                "arguments": {
                    "query": case.title,
                    "ward": case.ward,
                    "jurisdiction": case.jurisdiction,
                },
                "reasoning": "Determine official department jurisdiction based on verified knowledge.",
                "knowledge_context": knowledge_results,
            }
