"""case-insensitive unique index on competitor_registry.source_id

Revision ID: b2c3d4e5f6a7
Revises: 534e861845d0
Create Date: 2026-10-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = '534e861845d0'
branch_labels = None
depends_on = None


def _index_exists(bind, table: str, index_name: str) -> bool:
    """Check whether an index physically exists on the given table.

    SQLAlchemy's inspector cannot reflect expression-based indexes (it
    warns and skips them), so we query the dialect's native catalog
    directly. This keeps the migration idempotent on installs that
    pre-created tables through Base.metadata.create_all().
    """
    name = bind.dialect.name
    if name == "sqlite":
        rows = bind.exec_driver_sql(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        ).fetchall()
        return bool(rows)
    if name in ("postgresql", "postgres"):
        rows = bind.exec_driver_sql(
            "SELECT 1 FROM pg_indexes WHERE indexname=?",
            (index_name,),
        ).fetchall()
        return bool(rows)
    # Generic fallback for any other dialect.
    try:
        return bool(bind.dialect.has_index(bind, table, index_name))
    except Exception:
        return False


def upgrade():
    # The app-level dedup check uses func.lower(source_id), but the column
    # itself only had a case-sensitive unique constraint. Concurrent requests
    # with case variants (byjus / BYJUS) could both pass the check and one
    # would blow up with a raw IntegrityError instead of a clean 400.
    # Add a case-insensitive unique index so the database enforces the same
    # invariant the application intends. Works on both SQLite and PostgreSQL.
    bind = op.get_bind()
    if not _index_exists(bind, "competitor_registry", "ix_competitor_registry_source_id_lower"):
        op.create_index(
            "ix_competitor_registry_source_id_lower",
            "competitor_registry",
            [sa.text("LOWER(source_id)")],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()
    if _index_exists(bind, "competitor_registry", "ix_competitor_registry_source_id_lower"):
        op.drop_index(
            "ix_competitor_registry_source_id_lower",
            table_name="competitor_registry",
        )