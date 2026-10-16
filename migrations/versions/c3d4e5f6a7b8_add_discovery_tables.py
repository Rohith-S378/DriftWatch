"""add discovery runs and candidates tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "discovery_runs" not in tables:
        op.create_table(
            "discovery_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("target_url", sa.String(), nullable=False),
            sa.Column("normalized_domain", sa.String(), nullable=False, index=True),
            sa.Column("company_name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), server_default="completed"),
            sa.Column("company_profile", sa.JSON(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if "discovery_candidates" not in tables:
        op.create_table(
            "discovery_candidates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), nullable=False, index=True),
            sa.Column("candidate_name", sa.String(), nullable=False),
            sa.Column("website_url", sa.String(), nullable=False),
            sa.Column("normalized_domain", sa.String(), nullable=False, index=True),
            sa.Column("match_score", sa.Float(), nullable=False),
            sa.Column("classification", sa.String(), nullable=False),
            sa.Column("classification_reason", sa.Text(), nullable=True),
            sa.Column("match_explanation", sa.Text(), nullable=False),
            sa.Column("is_verified", sa.Boolean(), server_default="0"),
            sa.Column("evidence", sa.JSON(), nullable=True),
            sa.Column("missing_evidence", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), server_default="suggested"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table("discovery_candidates")
    op.drop_table("discovery_runs")
