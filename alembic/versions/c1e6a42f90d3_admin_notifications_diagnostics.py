"""Добавить единый центр уведомлений и диагностику Notes.

Revision ID: c1e6a42f90d3
Revises: b7d4e2f190ab
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c1e6a42f90d3"
down_revision = "b7d4e2f190ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("license_id", sa.String(length=128), nullable=True),
        sa.Column("customer", sa.String(length=160), nullable=True),
        sa.Column("client_version", sa.String(length=64), nullable=True),
        sa.Column("client_version_code", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("package_name", sa.String(length=220), nullable=True),
        sa.Column("package_path", sa.Text(), nullable=True),
        sa.Column("package_size", sa.BigInteger(), nullable=True),
        sa.Column("package_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_diagnostic_reports_installation_id", "diagnostic_reports", ["installation_id"])
    op.create_index("ix_diagnostic_reports_license_id", "diagnostic_reports", ["license_id"])
    op.create_index("ix_diagnostic_reports_client_version", "diagnostic_reports", ["client_version"])
    op.create_index("ix_diagnostic_reports_created_at", "diagnostic_reports", ["created_at"])

    op.create_table(
        "admin_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("push_status", sa.String(length=16), nullable=False),
        sa.Column("push_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("push_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="SET NULL"),
    )
    for name, columns in (
        ("ix_admin_notifications_site_id", ["site_id"]),
        ("ix_admin_notifications_kind", ["kind"]),
        ("ix_admin_notifications_severity", ["severity"]),
        ("ix_admin_notifications_source_type", ["source_type"]),
        ("ix_admin_notifications_source_id", ["source_id"]),
        ("ix_admin_notifications_status", ["status"]),
        ("ix_admin_notifications_push_status", ["push_status"]),
        ("ix_admin_notifications_created_at", ["created_at"]),
    ):
        op.create_index(name, "admin_notifications", columns)

    # Старые обращения сразу попадают в новый Inbox.
    op.execute(
        sa.text(
            """
            INSERT INTO admin_notifications (
                id, site_id, kind, severity, title, summary,
                source_type, source_id, status, details,
                push_status, created_at, read_at
            )
            SELECT
                gen_random_uuid(),
                site_id,
                'contact',
                'info',
                COALESCE(NULLIF(subject, ''), 'Новое обращение'),
                LEFT(name || ' · ' || message, 1000),
                'contact',
                id::text,
                CASE WHEN status = 'new' THEN 'new' ELSE 'read' END,
                jsonb_build_object('name', name, 'reply_to', reply_to),
                'skipped',
                created_at,
                read_at
            FROM contact_messages
            """
        )
    )


def downgrade() -> None:
    op.drop_table("admin_notifications")
    op.drop_table("diagnostic_reports")
