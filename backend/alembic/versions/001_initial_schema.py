"""Initial schema with pgvector and append-only timeline

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-09

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from backend.app.models.custom_types import CompatibleVector, CompatibleJSON

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension if on postgres
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="CITIZEN"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 3. Cases table
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("issue_category", sa.String(50), nullable=False),
        sa.Column("location_text", sa.String(500), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("ward", sa.String(100), nullable=False),
        sa.Column("jurisdiction", sa.String(150), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="OPEN"),
        sa.Column("verification_state", sa.String(50), nullable=False, server_default="AWAITING_VERIFICATION"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("issue_category IN ('GARBAGE', 'DRAINAGE', 'OTHER')", name="check_case_issue_category"),
        sa.CheckConstraint("status IN ('OPEN', 'MONITORING', 'CLOSED')", name="check_case_status"),
        sa.CheckConstraint(
            "verification_state IN ('AWAITING_VERIFICATION', 'CITIZEN_CONFIRMED_RESOLVED', 'RESOLUTION_DISPUTED', 'INSUFFICIENT_EVIDENCE')",
            name="check_case_verification_state",
        ),
    )

    # 4. Complaint Records table (immutable)
    op.create_table(
        "complaint_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=True, index=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("official_status", sa.String(50), nullable=False),
        sa.Column("official_status_retrieved_at", sa.DateTime(), nullable=True),
        sa.Column("retrieval_method", sa.String(50), nullable=False),
        sa.Column("extracted_json", CompatibleJSON, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "retrieval_method IN ('USER_ENTERED', 'IMPORTED_RECEIPT', 'SCREENSHOT_OCR', 'AUTHORISED_CONNECTOR', 'MOCK')",
            name="check_complaint_retrieval_method",
        ),
    )

    # 5. Case Link Suggestions
    op.create_table(
        "case_link_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("record_a", sa.Integer(), sa.ForeignKey("complaint_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_b", sa.Integer(), sa.ForeignKey("complaint_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("evidence_json", CompatibleJSON, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PROPOSED"),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('PROPOSED', 'APPROVED', 'REJECTED')", name="check_link_suggestion_status"),
    )

    # 6. Evidence table
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("mime", sa.String(100), nullable=False),
        sa.Column("exif_json", CompatibleJSON, nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("supplied_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provenance", sa.String(150), nullable=False),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 7. Timeline Events table (append-only)
    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("origin", sa.String(50), nullable=False, index=True),
        sa.Column("actor", sa.String(150), nullable=False),
        sa.Column("source", sa.String(150), nullable=False),
        sa.Column("payload_json", CompatibleJSON, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "origin IN ('SOURCE_FACT', 'USER_CLAIM', 'AI_RECOMMENDATION', 'SYSTEM_EVENT')",
            name="check_timeline_origin",
        ),
    )

    # 8. Tasks table
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("task_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING", index=True),
        sa.Column("run_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload_json", CompatibleJSON, nullable=False),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')", name="check_task_status"),
    )

    # 9. Approvals table
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("draft_json", CompatibleJSON, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="check_approval_status"),
    )

    # 10. Knowledge Chunks table
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("department", sa.String(150), nullable=False),
        sa.Column("jurisdiction", sa.String(150), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", CompatibleVector(dim=768), nullable=True),
        sa.Column("last_verified", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )

    # 11. Add Append-Only Database Triggers on timeline_events
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                CREATE OR REPLACE FUNCTION block_timeline_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'timeline_events is append-only. UPDATE and DELETE operations are forbidden.';
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trg_timeline_events_no_update ON timeline_events;
                CREATE TRIGGER trg_timeline_events_no_update
                BEFORE UPDATE ON timeline_events
                FOR EACH ROW EXECUTE FUNCTION block_timeline_mutation();

                DROP TRIGGER IF EXISTS trg_timeline_events_no_delete ON timeline_events;
                CREATE TRIGGER trg_timeline_events_no_delete
                BEFORE DELETE ON timeline_events
                FOR EACH ROW EXECUTE FUNCTION block_timeline_mutation();
                """
            )
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            sa.text(
                """
                CREATE TRIGGER IF NOT EXISTS trg_timeline_events_no_update
                BEFORE UPDATE ON timeline_events
                BEGIN
                    SELECT RAISE(ABORT, 'timeline_events is append-only. UPDATE operations are forbidden.');
                END;
                """
            )
        )
        op.execute(
            sa.text(
                """
                CREATE TRIGGER IF NOT EXISTS trg_timeline_events_no_delete
                BEFORE DELETE ON timeline_events
                BEGIN
                    SELECT RAISE(ABORT, 'timeline_events is append-only. DELETE operations are forbidden.');
                END;
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_timeline_events_no_update ON timeline_events;"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_timeline_events_no_delete ON timeline_events;"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS block_timeline_mutation();"))

    op.drop_table("knowledge_chunks")
    op.drop_table("approvals")
    op.drop_table("tasks")
    op.drop_table("timeline_events")
    op.drop_table("evidence")
    op.drop_table("case_link_suggestions")
    op.drop_table("complaint_records")
    op.drop_table("cases")
    op.drop_table("users")
