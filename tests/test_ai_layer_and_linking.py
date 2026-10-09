"""
Unit and Integration Tests for CivicLoop Open-Weight AI Layer and Feature 1 (Case Continuity)
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from backend.app.ai.llm import OpenWeightLLMClient
from backend.app.ai.extraction import (
    extract_from_text,
    ExtractedComplaintData,
)
from backend.app.domain.case_linking import (
    haversine_distance_meters,
    cosine_similarity,
    compute_signals,
    get_deterministic_text_embedding,
    AUTO_LINK_THRESHOLD,
    SUGGEST_LINK_THRESHOLD,
)
from backend.app.models.case import Case


# ----------------------------------------------------------------------
# 1. Hard Constraint Tests: Open-Weight Endpoint Enforcement
# ----------------------------------------------------------------------
def test_forbidden_endpoints_rejected():
    """Verify that proprietary closed model APIs are strictly blocked."""
    with pytest.raises(ValueError, match="HARD CONSTRAINT VIOLATION"):
        OpenWeightLLMClient(base_url="https://api.openai.com/v1")

    with pytest.raises(ValueError, match="HARD CONSTRAINT VIOLATION"):
        OpenWeightLLMClient(base_url="https://api.anthropic.com/v1")

    with pytest.raises(ValueError, match="HARD CONSTRAINT VIOLATION"):
        OpenWeightLLMClient(base_url="https://generativelanguage.googleapis.com/v1")


def test_allowed_open_weight_endpoints():
    """Verify valid open-weight endpoints are accepted."""
    client1 = OpenWeightLLMClient(base_url="http://localhost:8000/v1")
    assert client1.base_url == "http://localhost:8000/v1"

    client2 = OpenWeightLLMClient(base_url="http://localhost:11434/v1")
    assert client2.base_url == "http://localhost:11434/v1"


# ----------------------------------------------------------------------
# 2. Structured Chat with Repair Retry Test
# ----------------------------------------------------------------------
@pytest.mark.anyio
async def test_structured_chat_repair_retry():
    """Verify structured_chat automatically triggers repair retry when first response is invalid JSON."""
    client = OpenWeightLLMClient(base_url="http://mock-vllm:8000/v1")

    mock_bad_response = {
        "choices": [{"message": {"content": "This is not json {bad_key: 123"}}]
    }
    mock_good_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "complaint_number": "BBMP-2026-9912",
                            "source": "BBMP Sahaaya 2.0",
                            "category": "GARBAGE",
                            "location_text": "Indiranagar 100ft Rd",
                            "confidence": 0.95,
                            "field_confidences": {"complaint_number": 0.95},
                        }
                    )
                }
            }
        ]
    }

    with patch.object(client, "chat", AsyncMock(side_effect=[mock_bad_response, mock_good_response])):
        result = await client.structured_chat(
            messages=[{"role": "user", "content": "Extract complaint"}],
            response_model=ExtractedComplaintData,
            purpose="test_repair",
        )
        assert result.complaint_number == "BBMP-2026-9912"
        assert result.category == "GARBAGE"


# ----------------------------------------------------------------------
# 3. Extraction Pipeline Tests
# ----------------------------------------------------------------------
@pytest.mark.anyio
async def test_extraction_flags_low_confidence():
    """Verify that fields with confidence < 0.7 are flagged for citizen review."""
    mock_data = ExtractedComplaintData(
        complaint_number="SWACH-4412",
        source="Swachhata",
        category="DRAINAGE",
        location_text=None,
        confidence=0.65,
        field_confidences={"complaint_number": 0.9, "category": 0.85, "location_text": 0.4},
    )

    with patch("backend.app.ai.extraction.llm_client.structured_chat", AsyncMock(return_value=mock_data)):
        res = await extract_from_text("Grievance ref SWACH-4412 drainage issue")
        assert res.needs_review is True
        assert "location_text" in res.low_confidence_fields


# ----------------------------------------------------------------------
# 4. Geospatial and Embedding Mathematics Tests
# ----------------------------------------------------------------------
def test_haversine_distance():
    """Verify distance between two known Bengaluru landmarks (Indiranagar to Domlur ~1.9km)."""
    dist = haversine_distance_meters(12.9784, 77.6408, 12.9600, 77.6408)
    assert 1900 < dist < 2200


def test_cosine_similarity():
    """Verify cosine similarity calculation."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), 0.001) == 1.0

    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), 0.001) == 0.0


# ----------------------------------------------------------------------
# 5. Case Linking Signal & Composite Scoring Tests
# ----------------------------------------------------------------------
def test_case_linking_high_score_for_same_incident():
    """Verify high match score for cross-portal complaints reporting the same garbage blackspot."""
    embed1 = get_deterministic_text_embedding("GARBAGE Indiranagar 100ft road near Toit")
    embed2 = get_deterministic_text_embedding("GARBAGE 100 Feet Rd Indiranagar opp Toit")

    score, signals, explanation = compute_signals(
        complaint_category="GARBAGE",
        complaint_location_text="Opposite Toit, 100 Feet Road, Indiranagar",
        complaint_lat=12.9784,
        complaint_lng=77.6408,
        complaint_ward="Ward 112 Indiranagar",
        complaint_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        complaint_embed=embed1,
        case_category="GARBAGE",
        case_location_text="100ft Road Indiranagar near Toit pub",
        case_lat=12.9785,
        case_lng=77.6409,
        case_ward="112 - Domlur / Indiranagar",
        case_date=datetime(2026, 3, 2, tzinfo=timezone.utc),
        case_embed=embed2,
    )

    assert score >= SUGGEST_LINK_THRESHOLD
    assert signals.category_match is True
    assert signals.ward_match is True
    assert signals.geo_distance_meters is not None and signals.geo_distance_meters < 30.0
    assert "exact GPS match" in explanation


def test_case_linking_low_score_for_unrelated_incidents():
    """Verify low score for different categories across different Bengaluru zones."""
    embed1 = get_deterministic_text_embedding("GARBAGE Whitefield Hope Farm")
    embed2 = get_deterministic_text_embedding("DRAINAGE Malleshwaram 8th Cross")

    score, signals, explanation = compute_signals(
        complaint_category="GARBAGE",
        complaint_location_text="Hope Farm, Whitefield",
        complaint_lat=12.9830,
        complaint_lng=77.7516,
        complaint_ward="Ward 84 Whitefield",
        complaint_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        complaint_embed=embed1,
        case_category="DRAINAGE",
        case_location_text="8th Cross Margosa Rd Malleshwaram",
        case_lat=13.0031,
        case_lng=77.5702,
        case_ward="Ward 45 Malleshwaram",
        case_date=datetime(2026, 3, 25, tzinfo=timezone.utc),
        case_embed=embed2,
    )

    assert score < SUGGEST_LINK_THRESHOLD
    assert signals.category_match is False
    assert signals.ward_match is False


# ----------------------------------------------------------------------
# 6. API Endpoints Integration Tests (Mocked LLM)
# ----------------------------------------------------------------------
def test_ai_health_endpoint(client):
    """Test /api/ai/health returns open-weight model details."""
    response = client.get("/api/ai/health")
    assert response.status_code == 200
    data = response.json()
    assert "agent_model" in data
    assert "vision_model" in data
    assert "embed_model" in data


def test_extract_text_api(client, user1_token):
    """Test text extraction endpoint with mocked open-weight model."""
    mock_extracted = ExtractedComplaintData(
        complaint_number="BBMP-S-10492",
        source="BBMP Sahaaya 2.0",
        category="GARBAGE",
        location_text="12th Main Indiranagar",
        official_status="SUBMITTED",
        confidence=0.92,
        field_confidences={
            "complaint_number": 0.95,
            "source": 0.95,
            "category": 0.90,
            "location_text": 0.90,
            "official_status": 0.85,
        },
    )


    with patch("backend.app.ai.extraction.llm_client.structured_chat", AsyncMock(return_value=mock_extracted)):
        response = client.post(
            "/api/v1/ai/extract/text",
            json={"text": "BBMP Sahaaya Ref: BBMP-S-10492, Garbage dumped at 12th Main Indiranagar"},
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["data"]["complaint_number"] == "BBMP-S-10492"
        assert res_data["data"]["category"] == "GARBAGE"
        assert res_data["needs_review"] is False


def test_find_case_links_api(client, user1_token, db, test_users):
    """Test case linking candidate search endpoint."""
    user = test_users["user1"]
    
    test_case = Case(
        user_id=user.id,
        title="Overflowing Garbage at Indiranagar 100ft Rd",
        issue_category="GARBAGE",
        location_text="100 Feet Road, Indiranagar near Toit",
        lat=12.9784,
        lng=77.6408,
        ward="Ward 112 - Domlur / Indiranagar",
        jurisdiction="BBMP East Zone",
        status="OPEN",
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)

    response = client.post(
        "/api/v1/case-linking/find-links",
        json={
            "category": "GARBAGE",
            "location_text": "Opposite Toit pub, 100ft road Indiranagar",
            "lat": 12.9785,
            "lng": 77.6409,
            "ward": "Ward 112 - Domlur / Indiranagar",
        },
        headers={"Authorization": f"Bearer {user1_token}"},
    )
    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) >= 1
    top_match = candidates[0]
    assert top_match["case_id"] == test_case.id
    assert top_match["composite_score"] >= SUGGEST_LINK_THRESHOLD
    assert "explanation" in top_match

