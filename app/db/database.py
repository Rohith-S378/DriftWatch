from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import logging

# Check if using SQLite (no pooling options)
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    # SQLite configuration (no pooling)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )
else:
    # PostgreSQL configuration (with pooling)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Convenience export for scheduler and other services
async_session = AsyncSessionLocal

class Base(DeclarativeBase):
    pass

async def get_db():
    """FastAPI dependency for async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()