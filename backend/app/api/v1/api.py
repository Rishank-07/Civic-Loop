from fastapi import APIRouter
from backend.app.api.v1.endpoints import auth, cases, complaints, timeline

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(complaints.router, tags=["complaints"])
api_router.include_router(timeline.router, tags=["timeline"])
