import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import engine, Base, setup_database_triggers
from backend.app.api.v1.api import api_router
# Import all models to ensure metadata registration
import backend.app.models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civicloop")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing CivicLoop database schema and triggers...")
    Base.metadata.create_all(bind=engine)
    setup_database_triggers(engine)
    logger.info("CivicLoop initialization complete.")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Open-Source AI Agent for Persistent Civic Problem Management (Bengaluru)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CivicLoop Backend",
        "models": {
            "agent": settings.LLM_AGENT_MODEL,
            "vision": settings.LLM_VISION_MODEL,
            "embed": settings.EMBED_MODEL,
        },
    }
