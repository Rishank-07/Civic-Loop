from typing import Optional
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from backend.app.ai.llm import llm_client
from backend.app.ai.extraction import (
    extract_from_text,
    extract_from_screenshot,
    ExtractionResult,
)

router = APIRouter()


class TextExtractionRequest(BaseModel):
    text: str = Field(..., min_length=5, description="Raw complaint receipt text or grievance reference text")


class ScreenshotExtractionRequest(BaseModel):
    image_url: str = Field(..., description="Image URL or base64 data URI of the complaint screenshot")


@router.get("/health")
async def ai_health():
    """
    Open-weight model health check endpoint.
    Reports the active open-weight models (agent, vision, embed) and their status.
    This information is presented in the UI footer ('Powered by <model>').
    """
    health = await llm_client.health_check()
    return health


@router.post("/extract/text", response_model=ExtractionResult)
async def extract_complaint_from_text(payload: TextExtractionRequest):
    """
    Extracts structured complaint data from raw receipt text using the open-weight agent model.
    """
    try:
        result = await extract_from_text(payload.text)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(exc)}",
        )


@router.post("/extract/screenshot", response_model=ExtractionResult)
async def extract_complaint_from_screenshot(payload: ScreenshotExtractionRequest):
    """
    Extracts structured complaint data from a screenshot using the open-weight vision model (Qwen 3.6 VL).
    """
    try:
        result = await extract_from_screenshot(payload.image_url)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vision extraction failed: {str(exc)}",
        )
