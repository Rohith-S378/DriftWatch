"""add authentication tables (users, auth_identities, sessions)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-18 00:00:00.000000

Adds server-side session-based authentication:
- users: account record (email, optional password hash, display name)
- auth_identities: provider/subject pairs enforcing uniqueness per provider
- sessions: server-side session records keyed by an opaque random token

Also adds nullable user_id ownership columns to existing resource tables.
All new columns are nullable so existing data is preserved untouched.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # ── users ──────────────────────────────────────────────────────────────
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(), nullable=False, index=True),
            sa.Column("password_hash", sa.String(), nullable=True),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="1"),
            sa.Column("is_verified", sa.Boolean(), server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        )
        # Case-insensitive unique index on email (matches model invariant)
        op.create_index(
            "ix_users_email_lower",
            "users",
            [sa.text("lower(email)")],
            unique=True,
        )

    # ── auth_identities ────────────────────────────────────────────────────
    if "auth_identities" not in tables:
        op.create_table(
            "auth_identities",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False, index=True),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("provider_subject", sa.String(), nullable=False),
            sa.Column("provider_email", sa.String(), nullable=True),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_auth_identities_provider_subject",
            "auth_identities",
            ["provider", "provider_subject"],
            unique=True,
        )

    # ── sessions ───────────────────────────────────────────────────────────
    if "sessions" not in tables:
        op.create_table(
            "sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False, index=True),
            sa.Column("session_token", sa.String(), nullable=False, unique=True, index=True),
            sa.Column("user_agent_hash", sa.String(), nullable=True),
            sa.Column("ip_hash", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked", sa.Boolean(), server_default="0"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )

    # ── Ownership columns on existing resource tables (nullable = safe) ────
    _add_user_id_if_missing("data_snapshots", tables)
    _add_user_id_if_missing("change_events", tables)
    _add_user_id_if_missing("price_history", tables)
    _add_user_id_if_missing("competitor_registry", tables)
    _add_user_id_if_missing("discovery_runs", tables)
    _add_user_id_if_missing("discovery_candidates", tables)


def _add_user_id_if_missing(table_name, existing_tables):
    """Add a nullable user_id column to an existing resource table.

    The FK to users.id is deliberately NOT created here: SQLite does not
    support ALTER TABLE ADD CONSTRAINT, and PostgreSQL does not need it
    because the model declares the relationship. Authorization is enforced
    server-side in Python by the auth dependency, not by the DB FK.
    """
    if table_name in existing_tables:
        cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}
        if "user_id" not in cols:
            op.add_column(
                table_name,
                sa.Column("user_id", sa.String(36), nullable=True, index=True),
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    for t in ("data_snapshots", "change_events", "price_history",
              "competitor_registry", "discovery_runs", "discovery_candidates"):
        if t in tables:
            cols = {c["name"] for c in inspector.get_columns(t)}
            if "user_id" in cols:
                # SQLite keeps an index on the column (created by add_column
                # index=True); drop it first or ALTER DROP COLUMN fails.
                idx_name = f"ix_{t}_user_id"
                existing_indexes = {i["name"] for i in inspector.get_indexes(t)}
                if idx_name in existing_indexes:
                    op.drop_index(idx_name, table_name=t)
                op.drop_column(t, "user_id")

    if "sessions" in tables:
        op.drop_table("sessions")
    if "auth_identities" in tables:
        op.drop_table("auth_identities")
    if "users" in tables:
        op.drop_table("users")