"""
Test fixtures. Session/Message/Artifact CRUD is tested against an in-memory sqlite
DB (same ORM code path as Postgres) via dependency override — this validates the
API/persistence layer without requiring a live Postgres+pgvector instance.

`transcript_chunks` uses raw pgvector-specific SQL (the `<=>` operator, `VECTOR` type)
and is NOT portable to sqlite, so retrieval tests exercise TranscriptRetriever's
threshold/filtering *logic* against a mocked AsyncSession instead — see
test_retrieval.py for why that's still a meaningful test of the highest-risk path
(silent hallucination on weak matches), not a DB integration test.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base, get_db


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        from app.models import db_models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    from app.main import app

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"
