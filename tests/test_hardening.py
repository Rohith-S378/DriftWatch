"""
Hardening regression tests:
1. /webhook/ingest auth + payload contract (401 on bad secret, 422 on bad body).
2. Crawler resilience to malformed / adversarial HTML (no crash, no 500).
3. Webhook ingest baseline behaviour (first push stores snapshot, no phantom events).
"""
import pytest
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from app.models.models import DataSnapshot


def test_webhook_ingest_rejects_invalid_secret(client):
    res = client.post(
        "/webhook/ingest",
        json={"source_id": "s", "source_type": "pricing", "data": {}},
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert res.status_code == 401


def test_webhook_ingest_rejects_missing_fields(client):
    # Empty body
    assert client.post(
        "/webhook/ingest", json={}, headers={"X-Webhook-Secret": "test"}
    ).status_code == 422
    # Missing data
    assert client.post(
        "/webhook/ingest",
        json={"source_id": "s", "source_type": "pricing"},
        headers={"X-Webhook-Secret": "test"},
    ).status_code == 422
    # Extra forbidden field
    assert client.post(
        "/webhook/ingest",
        json={"source_id": "s", "source_type": "pricing", "data": {}, "x": 1},
        headers={"X-Webhook-Secret": "test"},
    ).status_code == 422


def test_webhook_ingest_baseline_no_phantom_events(client, engine):
    """First push for a source stores a snapshot and must not emit changes."""
    res = client.post(
        "/webhook/ingest",
        json={
            "source_id": "wh_base",
            "source_type": "pricing",
            "data": {"headline": "H", "plans": [{"name": "Pro", "price": "$10"}]},
        },
        headers={"X-Webhook-Secret": "test"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["changes_detected"] == 0
    assert body["events"] == []

    ev_res = client.get("/api/events/wh_base")
    assert ev_res.status_code == 200
    assert ev_res.json() == []

    # Snapshot must have been persisted
    import asyncio
    from sqlalchemy import select, func

    async def _count():
        async with engine.connect() as conn:
            r = await conn.execute(
                select(func.count(DataSnapshot.id)).where(
                    DataSnapshot.source_id == "wh_base"
                )
            )
            return r.scalar()

    assert asyncio.run(_count()) == 1


class MalformedHTMLServer(BaseHTTPRequestHandler):
    """Serves intentionally broken / adversarial HTML."""
    mode = "garbage"

    def do_GET(self):
        if MalformedHTMLServer.mode == "garbage":
            body = b"<html><body><div class='pricing-plan'><h3>Pro</h3>"
            ctype = "text/html"
        elif MalformedHTMLServer.mode == "empty":
            body = b""
            ctype = "text/html"
        else:  # binary
            body = b"\x00\x01\x02\xff\xfe<not html at all>"
            ctype = "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def malformed_server():
    server = HTTPServer(("127.0.0.1", 0), MalformedHTMLServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.mark.asyncio
async def test_crawler_malformed_html_no_crash(client, malformed_server):
    """Unclosed tags / empty body / binary garbage must never produce a 500.

    The guarantee is that the endpoint always returns HTTP 200 with a
    well-formed CrawlResult (success True or False) — never a 500, never an
    unhandled exception. Binary garbage that aiohttp cannot decode as UTF-8
    is a legitimate fetch failure, so success=False is acceptable there.
    """
    from app.config import settings

    original = settings.ALLOW_LOCAL_CRAWLS
    settings.ALLOW_LOCAL_CRAWLS = True
    try:
        for mode in ("garbage", "empty", "binary"):
            MalformedHTMLServer.mode = mode
            res = client.post(
                "/api/crawl/single",
                json={"source_id": "malformed_comp", "url": malformed_server},
            )
            assert res.status_code == 200, f"mode={mode} returned {res.status_code}"
            data = res.json()
            # Well-formed response envelope, never a 500.
            assert isinstance(data["success"], bool)
            assert isinstance(data["pricing"], list)
            assert isinstance(data["keywords"], list)
            assert isinstance(data["headline"], str)
            # HTML that parses (garbage/empty) must succeed and yield empty
            # extraction; binary garbage is a fetch failure, not a crash.
            if mode in ("garbage", "empty"):
                assert data["success"] is True, f"mode={mode}: {data.get('error')}"
    finally:
        settings.ALLOW_LOCAL_CRAWLS = original


@pytest.mark.asyncio
async def test_persistence_across_restart(tmp_path):
    """Verify that competitors, snapshots, and events persist across engine restarts.
    Uses an isolated file SQLite database (NOT sirius.db).
    """
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.db.database import Base
    from app.models.models import CompetitorRegistry, DataSnapshot, ChangeEvent
    from sqlalchemy import select

    test_db_path = str(tmp_path / "test_restart.db")
    db_url = f"sqlite+aiosqlite:///{test_db_path}"

    # 1. Start Engine 1: Create schema and write data
    engine1 = create_async_engine(db_url, echo=False)
    async with engine1.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session1 = async_sessionmaker(engine1, class_=AsyncSession, expire_on_commit=False)
    async with Session1() as session:
        comp = CompetitorRegistry(source_id="RestartCorp", url="https://restart.example.com")
        snap = DataSnapshot(source_id="RestartCorp", source_type="pricing", payload={"headline": "Test 1"})
        ev = ChangeEvent(
            source_id="RestartCorp",
            change_type="price",
            severity="high",
            description="Price increased",
            old_value="10",
            new_value="20",
        )
        session.add_all([comp, snap, ev])
        await session.commit()

    # Simulate shutdown: dispose engine 1
    await engine1.dispose()

    # 2. Restart: Start Engine 2 on the same isolated DB file
    engine2 = create_async_engine(db_url, echo=False)
    Session2 = async_sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)
    async with Session2() as session:
        res_comp = await session.execute(select(CompetitorRegistry).where(CompetitorRegistry.source_id == "RestartCorp"))
        assert res_comp.scalar_one_or_none() is not None

        res_snap = await session.execute(select(DataSnapshot).where(DataSnapshot.source_id == "RestartCorp"))
        snap_rec = res_snap.scalar_one_or_none()
        assert snap_rec is not None
        assert snap_rec.payload == {"headline": "Test 1"}

        res_ev = await session.execute(select(ChangeEvent).where(ChangeEvent.source_id == "RestartCorp"))
        ev_rec = res_ev.scalar_one_or_none()
        assert ev_rec is not None
        assert ev_rec.description == "Price increased"

    await engine2.dispose()
