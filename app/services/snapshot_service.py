from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Any
from datetime import datetime, timedelta

from app.models.models import DataSnapshot, ChangeEvent, PriceHistory
from app.models.schemas import WebhookPayload, ChangeEventOut, ProcessResult
from app.services.change_detector import (
    detect_price_changes,
    detect_keyword_changes,
    detect_messaging_changes,
    detect_price_anomaly,
    ChangeResult,
)
from app.services.extractors import extract_price, extract_currency
import json

def _serialize_diff(diff: Any) -> Any:
    """Convert DeepDiff result (PrettyOrderedSet etc.) to plain JSON-serializable dict."""
    if diff is None:
        return None
    try:
        return json.loads(json.dumps(diff, default=lambda o: list(o) if hasattr(o, '__iter__') else str(o)))
    except Exception:
        return str(diff)

async def _is_flap(change: ChangeResult, db: AsyncSession, source_id: str, window_seconds: int = 300, max_distinct: int = 3) -> bool:
    """
    Detect if the current change is a flap (returns to a recent value after only a few distinct
    intermediate values) within the given time window.
    Returns True if the current new_value matches a previous value and the number of distinct
    values between that previous occurrence and now does not exceed `max_distinct`.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    stmt = (
        select(ChangeEvent)
        .where(ChangeEvent.source_id == source_id)
        .where(ChangeEvent.change_type == change.change_type)
        .where(ChangeEvent.created_at >= cutoff)
        .order_by(desc(ChangeEvent.created_at))
        .limit(100)  # safety bound
    )
    result = await db.execute(stmt)
    recent = result.scalars().all()  # newest first

    # Build chronological list from oldest to newest
    history = [(ev.old_value, ev.new_value) for ev in reversed(recent)]
    # Append current change
    history.append((change.old_value, change.new_value))

    # Flatten to a simple list of values
    seq = []
    for old, new in history:
        seq.append(old)
        seq.append(new)

    cur_idx = len(seq) - 1  # index of current new_value
    cur_new = seq[cur_idx]

    # Scan backwards for a previous occurrence of the same new value
    for j in range(cur_idx - 1, -1, -1):
        if seq[j] == cur_new:
            # Calculate distinct values between j+1 and cur_idx-1 inclusive
            between = set(seq[j+1:cur_idx])  # excludes the matched old value and current new
            if len(between) <= max_distinct:
                return True
            # else continue looking for an earlier match
    return False

async def process_webhook(payload: WebhookPayload, db: AsyncSession) -> ProcessResult:
    """
    Main orchestrator:
      1. Save new snapshot
      2. Load previous snapshot for this source
      3. Run all detectors
      4. Persist change events
      5. Return structured result
    """
    # 1. Save snapshot
    snapshot = DataSnapshot(
        source_id=payload.source_id,
        source_type=payload.source_type,
        payload=payload.data,
    )
    db.add(snapshot)
    await db.flush()  # get the ID before commit

    # 2. Load previous snapshot
    result = await db.execute(
        select(DataSnapshot)
        .where(DataSnapshot.source_id == payload.source_id)
        .where(DataSnapshot.id != snapshot.id)
        .order_by(desc(DataSnapshot.created_at))
        .limit(1)
    )
    previous = result.scalar_one_or_none()

    all_changes: list[ChangeResult] = []

    if previous:
        old_data: dict[str, Any] = previous.payload
        new_data: dict[str, Any] = payload.data

        # 3a. Pricing changes
        old_plans = old_data.get("plans", [])
        new_plans = new_data.get("plans", [])
        if old_plans or new_plans:
            all_changes.extend(detect_price_changes(old_plans, new_plans))

        # 3b. Keyword changes
        old_kw = old_data.get("keywords", [])
        new_kw = new_data.get("keywords", [])
        context = new_data.get("headline", "") + " " + new_data.get("description", "")
        all_changes.extend(detect_keyword_changes(old_kw, new_kw, context))

        # 3c. Messaging / headline changes
        all_changes.extend(await detect_messaging_changes(old_data, new_data, db, payload.source_id))

    # 4. Save price history + run anomaly detection
    for plan in payload.data.get("plans", []):
        price = extract_price(str(plan.get("price", "")))
        currency = extract_currency(str(plan.get("price", "")))
        plan_name = plan.get("name", "unknown")

        if price is not None:
            ph = PriceHistory(
                source_id=payload.source_id,
                plan_name=plan_name,
                price=price,
                currency=currency,
            )
            db.add(ph)

            # Load history for anomaly check
            hist_result = await db.execute(
                select(PriceHistory.price)
                .where(PriceHistory.source_id == payload.source_id)
                .where(PriceHistory.plan_name == plan_name)
                .order_by(desc(PriceHistory.recorded_at))
                .limit(50)
            )
            history = [row[0] for row in hist_result.fetchall()] + [price]

            anomaly = detect_price_anomaly(plan_name, history, price)
            if anomaly:
                all_changes.append(anomaly)

    # 5. Persist change events
    event_rows: list[ChangeEvent] = []
    for change in all_changes:
        # Flap detection – downgrade to info if we see a flap (returning to a recent value after few distinct changes)
        if await _is_flap(change, db, payload.source_id):
            change.severity = "low"
            change.description = (
                f"This field appears to rotate between a small set of variants on {payload.source_id}'s site "
                "— likely A/B testing or dynamic content, not a deliberate strategy change."
            )
        event = ChangeEvent(
            source_id=payload.source_id,
            change_type=change.change_type,
            severity=change.severity,
            description=change.description,
            diff=_serialize_diff(change.diff),
            old_value=change.old_value,
            new_value=change.new_value,
        )
        db.add(event)
        event_rows.append(event)

    await db.commit()

    return ProcessResult(
        source_id=payload.source_id,
        snapshot_id=snapshot.id,
        changes_detected=len(all_changes),
        events=[ChangeEventOut.model_validate(e) for e in event_rows],
    )


async def get_recent_events(
    source_id: str, limit: int, db: AsyncSession
) -> list[ChangeEventOut]:
    result = await db.execute(
        select(ChangeEvent)
        .where(ChangeEvent.source_id == source_id)
        .order_by(desc(ChangeEvent.created_at))
        .limit(limit)
    )
    return [ChangeEventOut.model_validate(r) for r in result.scalars().all()]