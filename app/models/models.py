from sqlalchemy import Column, String, Float, JSON, DateTime, Text, Boolean, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.database import Base


class DataSnapshot(Base):
    """Stores every incoming webhook payload as a versioned snapshot."""
    __tablename__ = "data_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String, nullable=False, index=True)   # identifies the data source
    source_type = Column(String, nullable=False)              # e.g. "pricing", "messaging"
    payload = Column(JSON, nullable=False)                    # raw webhook data
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChangeEvent(Base):
    """Records every detected change with full diff detail."""
    __tablename__ = "change_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String, nullable=False, index=True)
    change_type = Column(String, nullable=False)   # "price", "keyword", "messaging", "anomaly"
    severity = Column(String, nullable=False)       # "low", "medium", "high", "critical"
    diff = Column(JSON, nullable=True)              # structured diff result
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceHistory(Base):
    """Time-series of extracted prices for anomaly detection."""
    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String, nullable=False, index=True)
    plan_name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class CompetitorRegistry(Base):
    """Stores competitor URLs and selector templates for crawling."""
    __tablename__ = "competitor_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String, nullable=False, unique=True, index=True)  # e.g. "competitor_name"
    url = Column(String, nullable=False)  # URL to crawl
    headline_selector = Column(String, nullable=True)  # CSS selector for headline
    price_selector = Column(String, nullable=True)  # CSS selector for pricing plans
    feature_selector = Column(String, nullable=True)  # CSS selector for features (optional)
    keyword_extraction = Column(Boolean, default=True)  # whether to extract keywords from text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # The app-level dedup check uses func.lower(source_id), but the column's
    # case-sensitive unique constraint alone lets concurrent requests with
    # case variants (byjus / BYJUS) both pass the check and one blow up with
    # a raw IntegrityError instead of a clean 400. This case-insensitive
    # unique index enforces the same invariant the application intends.
    __table_args__ = (
        Index(
            "ix_competitor_registry_source_id_lower",
            text("LOWER(source_id)"),
            unique=True,
        ),
    )


class DiscoveryRun(Base):
    """Tracks a competitor discovery run initiated by entering a company website."""
    __tablename__ = "discovery_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_url = Column(String, nullable=False)
    normalized_domain = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False)
    status = Column(String, default="completed")  # "pending", "completed", "failed"
    company_profile = Column(JSON, nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DiscoveryCandidate(Base):
    """Stores discovered competitor candidates and user decisions."""
    __tablename__ = "discovery_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    candidate_name = Column(String, nullable=False)
    website_url = Column(String, nullable=False)
    normalized_domain = Column(String, nullable=False, index=True)
    match_score = Column(Float, nullable=False)
    classification = Column(String, nullable=False)  # "direct", "indirect", "adjacent"
    classification_reason = Column(Text, nullable=True)
    match_explanation = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)
    evidence = Column(JSON, nullable=True)
    missing_evidence = Column(JSON, nullable=True)
    status = Column(String, default="suggested")  # "suggested", "tracked", "dismissed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
