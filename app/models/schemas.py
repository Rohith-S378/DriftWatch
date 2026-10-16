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


class CrawlSingleRequest(BaseModel):
    source_id: str
    url: str


class AskAIRequest(BaseModel):
    question: str
    source_id: Optional[str] = None


class AskAIResponse(BaseModel):
    question: str
    answer: str
    evidence: list[dict[str, Any]]
    total_matches: int


# Discovery Schemas
class DiscoveryAnalyzeRequest(BaseModel):
    url: str


class DiscoveryCandidateOut(BaseModel):
    id: UUID
    candidate_name: str
    website_url: str
    normalized_domain: str
    match_score: float
    classification: str
    classification_reason: Optional[str] = None
    match_explanation: str
    is_verified: bool
    evidence: Optional[dict[str, Any]] = None
    missing_evidence: Optional[list[str]] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscoveryRunOut(BaseModel):
    id: UUID
    target_url: str
    normalized_domain: str
    company_name: str
    status: str
    company_profile: dict[str, Any]
    candidates: list[DiscoveryCandidateOut] = []
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrackCandidateRequest(BaseModel):
    candidate_id: UUID
    custom_name: Optional[str] = None