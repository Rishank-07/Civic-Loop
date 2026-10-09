"""
Mock Portal Connector for testing and demonstrations.
Explicitly labelled as simulated in all responses.
Supports scriptable status simulation (RESOLVED, IN_PROGRESS, UNAVAILABLE).
"""

from typing import Dict, Optional, Any
from backend.app.connectors.base import BasePortalConnector, StatusResult, StatusOutcome
from backend.app.models.complaint import ComplaintRecord


class MockPortalConnector(BasePortalConnector):
    """
    Simulated external civic portal connector.
    """
    _override_status: Dict[str, str] = {}
    _force_unavailable: bool = False

    @classmethod
    def set_mock_status(cls, external_id_or_source: str, status: str):
        cls._override_status[external_id_or_source] = status

    @classmethod
    def set_unavailable(cls, unavailable: bool = True):
        cls._force_unavailable = unavailable

    @classmethod
    def reset(cls):
        cls._override_status.clear()
        cls._force_unavailable = False

    def check_status(self, complaint_record: ComplaintRecord) -> StatusResult:
        label = f"{complaint_record.source or 'BBMP Sahaaya 2.0'} (Simulated / Mock Connector)"

        if self._force_unavailable:
            return StatusResult(
                outcome=StatusOutcome.UNAVAILABLE,
                external_status="UNAVAILABLE",
                is_closure=False,
                source_label=label,
                raw_payload={"error": "Connection timed out to municipal grievance server (503)"},
                message="External portal is currently unreachable. Recorded as 'unable to verify' (never assumed unchanged).",
            )

        # Check explicit overrides
        lookup_keys = [
            complaint_record.external_id or "",
            str(complaint_record.id),
            complaint_record.source,
            "DEFAULT",
        ]
        
        status_val = "IN_PROGRESS"
        for k in lookup_keys:
            if k in self._override_status:
                status_val = self._override_status[k]
                break

        is_closure = status_val.upper() in ("RESOLVED", "CLOSED", "ATTENDED", "COMPLETED")

        return StatusResult(
            outcome=StatusOutcome.OK,
            external_status=status_val,
            is_closure=is_closure,
            source_label=label,
            raw_payload={
                "external_id": complaint_record.external_id,
                "portal": complaint_record.source,
                "official_status": status_val,
                "closure_flag": is_closure,
                "mock_notice": "[Simulated / Mock Portal Connector - CivicLoop Test Harness]",
            },
            message=f"Official status retrieved: {status_val}",
        )
