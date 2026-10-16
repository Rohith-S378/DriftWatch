"""Tests for Alembic migration upgrade and downgrade.

Uses a temporary SQLite database so it never touches production data.
"""
import os
import tempfile
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point the app at a temporary SQLite database for the duration of the test."""
    db_path = tmp_path / "test_migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    yield db_path


def test_alembic_upgrade_and_downgrade(isolated_db):
    sqlite_url = f"sqlite:///{isolated_db}"
    async_sqlite_url = f"sqlite+aiosqlite:///{isolated_db}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", async_sqlite_url)

    # Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    # Verify tables exist
    sync_engine = create_engine(sqlite_url)
    inspector = inspect(sync_engine)
    tables = set(inspector.get_table_names())
    expected = {"data_snapshots", "change_events", "price_history", "competitor_registry", "discovery_runs", "discovery_candidates"}
    assert expected.issubset(tables)

    # Run downgrade to base
    command.downgrade(alembic_cfg, "base")

    # Verify tables were removed
    inspector = inspect(sync_engine)
    remaining = set(inspector.get_table_names())
    assert expected.isdisjoint(remaining)
    sync_engine.dispose()


def test_alembic_upgrade_is_idempotent(isolated_db):
    """Running upgrade twice must not fail even if tables already exist
    (e.g. from Base.metadata.create_all() at startup)."""
    sqlite_url = f"sqlite:///{isolated_db}"
    async_sqlite_url = f"sqlite+aiosqlite:///{isolated_db}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", async_sqlite_url)

    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")  # idempotent

    sync_engine = create_engine(sqlite_url)
    inspector = inspect(sync_engine)
    tables = set(inspector.get_table_names())
    expected = {"data_snapshots", "change_events", "price_history", "competitor_registry", "discovery_runs", "discovery_candidates"}
    assert expected.issubset(tables)
    sync_engine.dispose()


def test_case_insensitive_unique_index_created_by_migration(isolated_db):
    """The b2c3d4e5f6a7 migration must physically create a case-insensitive
    unique index on competitor_registry.source_id and it must reject case
    variants at the database level (independent of any app-level check).

    NOTE: SQLAlchemy's SQLite inspector cannot reflect expression-based
    indexes (it warns and skips them), so we inspect the raw sqlite_master
    table and verify functional enforcement directly.
    """
    import sqlite3

    async_sqlite_url = f"sqlite+aiosqlite:///{isolated_db}"
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", async_sqlite_url)

    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(str(isolated_db))
    try:
        index_sqls = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='competitor_registry'"
            )
        }
        assert "ix_competitor_registry_source_id_lower" in index_sqls, (
            f"case-insensitive unique index missing; found: {list(index_sqls)}"
        )
        sql = index_sqls["ix_competitor_registry_source_id_lower"]
        assert "LOWER(source_id)" in sql and "UNIQUE" in sql.upper(), (
            f"index is not a case-insensitive unique index: {sql}"
        )

        # Functional enforcement: a case variant must be rejected at the DB level.
        conn.execute(
            "INSERT INTO competitor_registry (id, source_id, url) VALUES (?, ?, ?)",
            ("00000000-0000-0000-0000-000000000001", "byjus", "https://byjus.com"),
        )
        conn.commit()
        try:
            conn.execute(
                "INSERT INTO competitor_registry (id, source_id, url) VALUES (?, ?, ?)",
                ("00000000-0000-0000-0000-000000000002", "BYJUS", "https://byjus.com"),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # expected
        else:
            raise AssertionError(
                "case-variant insert was accepted despite the unique index"
            )
    finally:
        conn.close()