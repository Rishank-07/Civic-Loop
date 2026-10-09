from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth,
    cases,
    complaints,
    timeline,
    ai,
    case_linking,
    agent,
    approvals,
    evidence,
    knowledge,
    notifications,
    demo,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(complaints.router, tags=["complaints"])
api_router.include_router(timeline.router, tags=["timeline"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(case_linking.router, prefix="/case-linking", tags=["case-linking"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(approvals.router, tags=["approvals"])
api_router.include_router(evidence.router, tags=["evidence"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])
