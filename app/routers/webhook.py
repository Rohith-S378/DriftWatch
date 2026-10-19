from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.schemas import WebhookPayload, ProcessResult, ChangeEventOut
from app.models.models import ChangeEvent
from app.services.snapshot_service import process_webhook, get_recent_events
from app.services.notifier import notify_node
from app.config import settings
from app.auth import require_user
from app.models.auth import User

router = APIRouter(prefix="/webhook", tags=["Webhook Ingestion"])


def _verify_secret(x_webhook_secret: str = Header(...)):
    """Simple shared-secret auth between your external sources and this engine."""
    if x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@router.post("/ingest", response_model=ProcessResult)
async def ingest_webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_secret),
):
    """
    Receive a push payload from an external source.
    Runs all change detectors and returns the result synchronously,
    then fires a background notification to Node.js.
    """
    result = await process_webhook(payload, db)
    # Notify Node.js asynchronously (errors logged, not raised)
    await notify_node(result)
    return result


@router.get("/events/{source_id}", response_model=list[ChangeEventOut])
async def get_events(
    source_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
):
    """Fetch recent change events for a given source, scoped to the caller's
    ownership (own rows + legacy/global rows). Requires authentication so
    competitor data cannot be harvested by unauthenticated callers."""
    return await get_recent_events(source_id, limit, db, user_id=user.id)
