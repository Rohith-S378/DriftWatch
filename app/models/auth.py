"""Authentication and session models for DriftWatch.

Security design:
- Server-side sessions stored in the database (not JWT, not localStorage).
- Passwords hashed with bcrypt via passlib; never stored plaintext.
- Session tokens are high-entropy UUIDs; the actual token never touches the
  client — only a random opaque cookie value is sent, mapped server-side.
- AuthIdentity tracks provider + subject so Google account linking can
  enforce uniqueness of (provider, subject) without trusting the email.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Index, text
from sqlalchemy import Uuid
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True, index=True)
    # Null for OAuth-only accounts; hashed with bcrypt for password accounts.
    password_hash = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    identities = relationship("AuthIdentity", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
    )


class AuthIdentity(Base):
    """Tracks how a user authenticates (password, google, etc.).

    Enforces uniqueness of (provider, provider_subject) so the same Google
    identity cannot be linked to multiple accounts.
    """

    __tablename__ = "auth_identities"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String, nullable=False)  # "password", "google"
    # For password provider, this is the email; for google, the Google sub claim.
    provider_subject = Column(String, nullable=False)
    provider_email = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    # Raw OAuth tokens are NOT stored here. Only the identity facts needed
    # for verification and re-authentication.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="identities")

    __table_args__ = (
        Index("ix_auth_identities_provider_subject", "provider", "provider_subject", unique=True),
    )


class Session(Base):
    """Server-side session record.

    The cookie value sent to the client is a random UUID; the actual session
    data lives here. Expiry is enforced by `expires_at`. Expired sessions are
    purged by a periodic cleanup or on next access.
    """

    __tablename__ = "sessions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Opaque random token stored in the HttpOnly cookie.
    session_token = Column(String, nullable=False, unique=True, index=True)
    # Optional: client fingerprint for basic session-binding (IP/User-Agent hash).
    user_agent_hash = Column(String, nullable=True)
    ip_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)

    user = relationship("User", back_populates="sessions")