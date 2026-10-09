"""
CivicLoop Feature 1 Evaluation: Cross-Portal Case Continuity Benchmark
======================================================================
Evaluates the case linking engine on a realistic benchmark dataset of
Bengaluru civic complaints across BBMP Sahaaya, Swachhata App,
BESCOM Namma 1912, and BWSSB.

Computes:
- Precision
- Recall
- F1-Score
- Average Evaluation Latency (ms)
- Breakdown by Match Confidence Threshold
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from backend.app.domain.case_linking import (
    compute_signals,
    get_deterministic_text_embedding,
    AUTO_LINK_THRESHOLD,
    SUGGEST_LINK_THRESHOLD,
)

# ----------------------------------------------------------------------
# Realistic Bengaluru Civic Complaints Benchmark Dataset
# ----------------------------------------------------------------------
BENCHMARK_PAIRS = [
    {
        "id": "PAIR-01",
        "description": "Same Indiranagar garbage blackspot across BBMP Sahaaya and Swachhata",
        "expected_link": True,
        "complaint_a": {
            "source": "BBMP Sahaaya 2.0",
            "category": "GARBAGE",
            "location_text": "Opposite Toit, 100 Feet Road, Indiranagar, Ward 112",
            "lat": 12.9784,
            "lng": 77.6408,
            "ward": "112 - Domlur / Indiranagar",
            "date": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "Swachhata App",
            "category": "GARBAGE",
            "location_text": "100ft Rd near Toit pub, huge garbage pile not cleared for 4 days",
            "lat": 12.9785,
            "lng": 77.6409,
            "ward": "Ward 112 Indiranagar",
            "date": datetime(2026, 3, 2, 14, 30, tzinfo=timezone.utc),
        },
    },
    {
        "id": "PAIR-02",
        "description": "Koramangala 5th block blocked storm water drain reported on BWSSB and BBMP",
        "expected_link": True,
        "complaint_a": {
            "source": "BWSSB Sahayaa",
            "category": "DRAINAGE",
            "location_text": "80 Feet Road, 5th Block Koramangala, near Sony World Signal",
            "lat": 12.9352,
            "lng": 77.6245,
            "ward": "151 - Koramangala",
            "date": datetime(2026, 3, 3, 9, 15, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "BBMP FixMyStreet",
            "category": "DRAINAGE",
            "location_text": "Sony Signal corner, 80ft rd Koramangala 5th block overflowing drain flooding road",
            "lat": 12.9354,
            "lng": 77.6247,
            "ward": "Ward 151 Koramangala",
            "date": datetime(2026, 3, 4, 11, 0, tzinfo=timezone.utc),
        },
    },
    {
        "id": "PAIR-03",
        "description": "Prematurely closed complaint reopened with identical coordinates in HSR Layout",
        "expected_link": True,
        "complaint_a": {
            "source": "BBMP Sahaaya 2.0",
            "category": "GARBAGE",
            "location_text": "27th Main, Sector 1, HSR Layout, near Agara Lake",
            "lat": 12.9165,
            "lng": 77.6492,
            "ward": "174 - HSR Layout",
            "date": datetime(2026, 3, 5, 8, 0, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "Namma Bengaluru App",
            "category": "GARBAGE",
            "location_text": "Agara lake boundary on 27th Main HSR Sector 1 waste dumping recurring",
            "lat": 12.9166,
            "lng": 77.6493,
            "ward": "Ward 174 HSR Layout",
            "date": datetime(2026, 3, 8, 16, 45, tzinfo=timezone.utc),
        },
    },
    {
        "id": "PAIR-04",
        "description": "Same ward (Indiranagar) but different streets and unrelated categories",
        "expected_link": False,
        "complaint_a": {
            "source": "BBMP Sahaaya",
            "category": "GARBAGE",
            "location_text": "12th Main Road, HAL 2nd Stage, Indiranagar",
            "lat": 12.9719,
            "lng": 77.6412,
            "ward": "112 - Domlur / Indiranagar",
            "date": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "BESCOM Namma 1912",
            "category": "OTHER",
            "location_text": "Old Airport Road near Manipal Hospital",
            "lat": 12.9592,
            "lng": 77.6534,
            "ward": "112 - Domlur / Indiranagar",
            "date": datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc),
        },
    },
    {
        "id": "PAIR-05",
        "description": "Same category (GARBAGE) but distant Bengaluru zones (Whitefield vs Malleshwaram)",
        "expected_link": False,
        "complaint_a": {
            "source": "BBMP Sahaaya",
            "category": "GARBAGE",
            "location_text": "ITPL Main Road, Hope Farm Junction, Whitefield",
            "lat": 12.9830,
            "lng": 77.7516,
            "ward": "84 - Hagadur / Whitefield",
            "date": datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "Swachhata App",
            "category": "GARBAGE",
            "location_text": "8th Cross, Margosa Road, Malleshwaram",
            "lat": 13.0031,
            "lng": 77.5702,
            "ward": "45 - Malleshwaram",
            "date": datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
        },
    },
    {
        "id": "PAIR-06",
        "description": "Same location text without GPS coordinates in Jayanagar 4th Block",
        "expected_link": True,
        "complaint_a": {
            "source": "BBMP Sahaaya",
            "category": "DRAINAGE",
            "location_text": "Near Jayanagar 4th Block BDA Complex 11th Main Road",
            "lat": None,
            "lng": None,
            "ward": "153 - Jayanagar",
            "date": datetime(2026, 3, 2, 8, 30, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "Swachhata App",
            "category": "DRAINAGE",
            "location_text": "11th Main Road opposite BDA Complex 4th Block Jayanagar drain choked",
            "lat": None,
            "lng": None,
            "ward": "Ward 153 - Jayanagar",
            "date": datetime(2026, 3, 4, 15, 0, tzinfo=timezone.utc),
        },
    },
    {
        "id": "PAIR-07",
        "description": "Different categories in Bellandur (Drainage vs Garbage) separated by 2km",
        "expected_link": False,
        "complaint_a": {
            "source": "BWSSB Sahayaa",
            "category": "DRAINAGE",
            "location_text": "Outer Ring Road, Ecospace junction, Bellandur",
            "lat": 12.9260,
            "lng": 77.6835,
            "ward": "150 - Bellandur",
            "date": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        },
        "complaint_b": {
            "source": "BBMP Sahaaya",
            "category": "GARBAGE",
            "location_text": "Green Glen Layout, Bellandur Lake back gate",
            "lat": 12.9372,
            "lng": 77.6698,
            "ward": "150 - Bellandur",
            "date": datetime(2026, 3, 15, 11, 30, tzinfo=timezone.utc),
        },
    },
]


def run_benchmark():
    print("=" * 70)
    print("CivicLoop Feature 1: Cross-Portal Case Continuity Benchmark")
    print("=" * 70)

    tp, fp, tn, fn = 0, 0, 0, 0
    total_time_ms = 0.0

    print(f"\nEvaluating {len(BENCHMARK_PAIRS)} benchmark pairs...\n")

    for item in BENCHMARK_PAIRS:
        c_a = item["complaint_a"]
        c_b = item["complaint_b"]
        expected = item["expected_link"]

        # Compute embeddings for both
        text_a = f"{c_a['category']} {c_a['location_text']} {c_a['ward']}"
        text_b = f"{c_b['category']} {c_b['location_text']} {c_b['ward']}"

        t0 = time.monotonic()
        embed_a = get_deterministic_text_embedding(text_a)
        embed_b = get_deterministic_text_embedding(text_b)

        score, signals, explanation = compute_signals(
            complaint_category=c_a["category"],
            complaint_location_text=c_a["location_text"],
            complaint_lat=c_a["lat"],
            complaint_lng=c_a["lng"],
            complaint_ward=c_a["ward"],
            complaint_date=c_a["date"],
            complaint_embed=embed_a,
            case_category=c_b["category"],
            case_location_text=c_b["location_text"],
            case_lat=c_b["lat"],
            case_lng=c_b["lng"],
            case_ward=c_b["ward"],
            case_date=c_b["date"],
            case_embed=embed_b,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        total_time_ms += latency_ms

        predicted_link = score >= SUGGEST_LINK_THRESHOLD

        if predicted_link and expected:
            tp += 1
            result_tag = "[PASS: TRUE POSITIVE]"
        elif predicted_link and not expected:
            fp += 1
            result_tag = "[FAIL: FALSE POSITIVE]"
        elif not predicted_link and not expected:
            tn += 1
            result_tag = "[PASS: TRUE NEGATIVE]"
        else:
            fn += 1
            result_tag = "[FAIL: FALSE NEGATIVE]"


        print(f"[{item['id']}] {item['description']}")
        print(f"  Score: {score:.3f} | Predicted: {predicted_link} | Expected: {expected} -> {result_tag}")
        print(f"  Rationale: {explanation}")
        print(f"  Latency: {latency_ms:.2f}ms\n")

    # Metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(BENCHMARK_PAIRS)
    avg_latency = total_time_ms / len(BENCHMARK_PAIRS)

    print("=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Total Test Cases:       {len(BENCHMARK_PAIRS)}")
    print(f"True Positives (TP):    {tp}")
    print(f"True Negatives (TN):    {tn}")
    print(f"False Positives (FP):   {fp}")
    print(f"False Negatives (FN):   {fn}")
    print("-" * 70)
    print(f"Accuracy:               {accuracy * 100:.1f}%")
    print(f"Precision:              {precision * 100:.1f}%")
    print(f"Recall:                 {recall * 100:.1f}%")
    print(f"F1-Score:               {f1 * 100:.1f}%")
    print(f"Avg Latency per pair:   {avg_latency:.2f}ms")
    print("=" * 70)

    assert f1 >= 0.85, f"Evaluation F1 score {f1} is below requirement (0.85)"
    print("\nBenchmark Passed Successfully!")


if __name__ == "__main__":
    run_benchmark()
