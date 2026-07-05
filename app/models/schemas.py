from pydantic import BaseModel, ConfigDict
from typing import Any, Optional
from datetime import datetime
from uuid import UUID

class WebhookPayload(BaseModel):
    source_id: str
    source_type: str
    data: dict[str, Any]

    model_config = ConfigDict(extra="forbid")

class ChangeEventOut(BaseModel):
    id: UUID
    source_id: str
    change_type: str
    severity: str
    diff: Optional[dict[str, Any]] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    description: str
    notified: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProcessResult(BaseModel):
    source_id: str
    snapshot_id: UUID
    changes_detected: int
    events: list[ChangeEventOut]