"""
Async SQLAlchemy engine/session setup. Tests override `DATABASE_URL` to a sqlite
in-memory DB via dependency override (see tests/conftest.py) so the same models and
retriever code path is exercised without requiring a live Postgres/pgvector instance.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables that don't require the pgvector extension (used by tests /
    first-run convenience). The `transcript_chunks` table with its VECTOR column and
    HNSW index is created by scripts/ingest.py against real Postgres, since sqlite
    (used in tests) has no vector type."""
    async with engine.begin() as conn:
        from app.models import db_models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
