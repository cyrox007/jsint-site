"""Добавить неизменяемый журнал control plane.

Revision ID: d4e9a61b7c20
Revises: c8d2f51a6e90
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4e9a61b7c20"
down_revision = "c8d2f51a6e90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "control_plane_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_label", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=True),
        sa.Column("target_id", sa.String(length=160), nullable=True),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("license_id", sa.String(length=128), nullable=True),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "actor_kind",
        "actor_user_id",
        "action",
        "outcome",
        "target_type",
        "target_id",
        "installation_id",
        "license_id",
        "release_id",
        "created_at",
    ):
        op.create_index(
            f"ix_control_plane_audit_{column}",
            "control_plane_audit",
            [column],
        )

    op.execute(
        """
        CREATE FUNCTION reject_control_plane_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'control_plane_audit is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_control_plane_audit_immutable
        BEFORE UPDATE OR DELETE ON control_plane_audit
        FOR EACH ROW EXECUTE FUNCTION reject_control_plane_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_control_plane_audit_immutable ON control_plane_audit")
    op.execute("DROP FUNCTION IF EXISTS reject_control_plane_audit_mutation()")
    op.drop_table("control_plane_audit")
