"""
Manual Update Connector for records entered or updated by officers/citizens.
"""

from backend.app.connectors.base import BasePortalConnector, StatusResult, StatusOutcome
from backend.app.models.complaint import ComplaintRecord


class ManualUpdateConnector(BasePortalConnector):
    """
    Connector for manually verified or entered complaint records.
    """

    def check_status(self, complaint_record: ComplaintRecord) -> StatusResult:
        label = "Manual Officer Verification"
        is_closure = complaint_record.official_status.upper() in ("RESOLVED", "CLOSED")

        return StatusResult(
            outcome=StatusOutcome.OK,
            external_status=complaint_record.official_status,
            is_closure=is_closure,
            source_label=label,
            raw_payload={
                "complaint_id": complaint_record.id,
                "manual_status": complaint_record.official_status,
            },
            message=f"Manual status maintained: {complaint_record.official_status}",
        )
