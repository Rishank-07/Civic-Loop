"""
CivicLoop Extraction Pipeline
==============================
Extracts structured complaint data from:
  - Complaint ID text
  - Pasted receipt text
  - Screenshot uploads (via open-weight vision model)

Outputs a validated Pydantic schema with confidence scores.
Low-confidence fields are flagged for citizen review before saving.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.ai.llm import llm_client

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Pydantic schema for extracted complaint data
# ------------------------------------------------------------------
class ExtractedComplaintData(BaseModel):
    """Structured output from the extraction pipeline."""
    complaint_number: Optional[str] = Field(None, description="Official complaint/grievance reference number")
    source: Optional[str] = Field(None, description="Portal or authority name (e.g. BBMP Sahaaya, Swachhata, Namma Bengaluru)")
    category: Optional[str] = Field(None, description="Issue category: GARBAGE, DRAINAGE, or OTHER")
    location_text: Optional[str] = Field(None, description="Physical address or landmark description")
    reported_date: Optional[str] = Field(None, description="Date the complaint was filed (ISO or natural language)")
    official_status: Optional[str] = Field(None, description="Current status as stated by authority (e.g. SUBMITTED, ASSIGNED, IN_PROGRESS, CLOSED)")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Overall extraction confidence 0..1")
    field_confidences: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence scores for citizen review (fields below 0.7 need attention)",
    )
    raw_extracted_text: Optional[str] = Field(None, description="Raw text extracted from vision model (screenshots only)")


class ExtractionResult(BaseModel):
    """Wrapper for extraction pipeline output with review flags."""
    data: ExtractedComplaintData
    needs_review: bool = Field(False, description="True if any field has confidence < 0.7")
    low_confidence_fields: List[str] = Field(default_factory=list, description="Fields the citizen should review and correct")


# ------------------------------------------------------------------
# Prompts
# ------------------------------------------------------------------
RECEIPT_TEXT_PROMPT = """You are an expert at extracting structured complaint data from Indian civic complaint receipts and portal text.

Extract the following fields from the provided text:
- complaint_number: The official grievance/complaint reference number
- source: The portal or authority (e.g. "BBMP Sahaaya 2.0", "Swachhata", "Namma Bengaluru")
- category: GARBAGE, DRAINAGE, or OTHER
- location_text: Physical address, ward, or landmark description
- reported_date: Date the complaint was filed (in ISO 8601 format if possible)
- official_status: The current official status (e.g. SUBMITTED, ASSIGNED, IN_PROGRESS, CLOSED, RESOLVED)
- confidence: Your overall confidence in the extraction (0.0 to 1.0)
- field_confidences: A JSON object mapping each field name to its individual confidence (0.0 to 1.0)

If a field cannot be determined from the text, set it to null and give it a confidence of 0.0.
Respond with ONLY valid JSON matching the schema."""

SCREENSHOT_VISION_PROMPT = """You are an expert at performing OCR and data extraction from Indian civic complaint portal screenshots (BBMP, Swachhata, Namma Bengaluru, etc).

First, read all visible text from the screenshot image.
Then extract these structured fields:
- complaint_number: The official grievance/complaint reference number visible in the screenshot
- source: The portal or authority name visible (e.g. "BBMP Sahaaya 2.0", "Swachhata App", "Namma Bengaluru")
- category: GARBAGE, DRAINAGE, or OTHER based on complaint type visible
- location_text: Physical address, ward, or landmark from the screenshot
- reported_date: Date the complaint was filed (ISO 8601 if possible)
- official_status: Current status shown in the screenshot (e.g. SUBMITTED, ASSIGNED, IN_PROGRESS, CLOSED)
- confidence: Your overall confidence in the extraction (0.0 to 1.0)
- field_confidences: A JSON object mapping each field to its confidence (0.0 to 1.0)
- raw_extracted_text: The full raw OCR text you extracted from the image

If a field cannot be determined, set it to null and confidence to 0.0.
Respond with ONLY valid JSON matching the schema."""


# ------------------------------------------------------------------
# Pipeline functions
# ------------------------------------------------------------------
async def extract_from_text(raw_text: str) -> ExtractionResult:
    """
    Extracts structured complaint data from pasted receipt text or
    complaint ID description using the open-weight agent model.
    """
    messages = [
        {"role": "system", "content": RECEIPT_TEXT_PROMPT},
        {"role": "user", "content": f"Extract structured data from this complaint text:\n\n{raw_text}"},
    ]

    extracted = await llm_client.structured_chat(
        messages=messages,
        response_model=ExtractedComplaintData,
        purpose="extraction_text",
    )

    return _build_result(extracted)


async def extract_from_screenshot(image_url: str) -> ExtractionResult:
    """
    Extracts structured complaint data from a screenshot image using
    the open-weight vision model (e.g. Qwen 3.6 VL).
    """
    # Step 1: Vision model extracts and OCRs the screenshot
    vision_response = await llm_client.vision_chat(
        prompt=SCREENSHOT_VISION_PROMPT,
        image_url=image_url,
        purpose="extraction_screenshot_ocr",
    )

    raw_content = vision_response["choices"][0]["message"]["content"]

    # Step 2: Parse the vision output into structured data
    try:
        # Try direct JSON parse first
        parsed = json.loads(raw_content)
        extracted = ExtractedComplaintData.model_validate(parsed)
    except (json.JSONDecodeError, Exception):
        # If vision model output isn't clean JSON, use agent model to clean it
        messages = [
            {"role": "system", "content": RECEIPT_TEXT_PROMPT},
            {"role": "user", "content": f"Extract structured data from this OCR output of a complaint screenshot:\n\n{raw_content}"},
        ]
        extracted = await llm_client.structured_chat(
            messages=messages,
            response_model=ExtractedComplaintData,
            purpose="extraction_screenshot_structured",
        )
        extracted.raw_extracted_text = raw_content

    return _build_result(extracted)


def _build_result(extracted: ExtractedComplaintData) -> ExtractionResult:
    """Compute review flags based on field confidences."""
    low_fields: List[str] = []
    review_threshold = 0.7

    # Check per-field confidences
    for field_name, conf in extracted.field_confidences.items():
        if conf < review_threshold:
            low_fields.append(field_name)

    # Also flag null required fields as needing review
    important_fields = ["complaint_number", "source", "category", "location_text", "official_status"]
    for f in important_fields:
        val = getattr(extracted, f, None)
        if val is None and f not in low_fields:
            low_fields.append(f)

    needs_review = len(low_fields) > 0 or extracted.confidence < review_threshold

    return ExtractionResult(
        data=extracted,
        needs_review=needs_review,
        low_confidence_fields=low_fields,
    )
