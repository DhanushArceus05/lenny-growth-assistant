"""
Regression test for the Railway production crash: managed Postgres providers
inject DATABASE_URL using the plain libpq scheme (`postgresql://`, sometimes the
legacy `postgres://`), not SQLAlchemy's driver-qualified `postgresql+asyncpg://`
that create_async_engine requires. Passing the plain scheme through unmodified
resolves to a sync driver and crashes the async engine at startup.
"""
import os

from app.config import Settings


def _settings_with(database_url: str) -> Settings:
    # Settings() reads from the process environment (and .env) at construction
    # time — set DATABASE_URL directly rather than going through get_settings()'s
    # cache, so each case in this file is independent of import/call order.
    os.environ["DATABASE_URL"] = database_url
    try:
        return Settings()
    finally:
        del os.environ["DATABASE_URL"]


def test_plain_postgresql_scheme_is_normalized_to_asyncpg():
    settings = _settings_with("postgresql://user:pass@railway.internal:5432/railway")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@railway.internal:5432/railway"


def test_legacy_postgres_scheme_is_normalized_to_asyncpg():
    settings = _settings_with("postgres://user:pass@railway.internal:5432/railway")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@railway.internal:5432/railway"


def test_already_correct_asyncpg_url_is_left_unchanged():
    settings = _settings_with("postgresql+asyncpg://user:pass@host:5432/db")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db"


def test_non_postgres_url_is_left_unchanged():
    """sqlite (used by the test suite's own DB fixtures) must not be touched by
    a normalization rule scoped to postgres schemes only."""
    settings = _settings_with("sqlite+aiosqlite:///:memory:")
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:"


def test_query_params_and_credentials_are_preserved_through_normalization():
    settings = _settings_with("postgresql://user:p%40ss@host:5432/db?sslmode=require")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:p%40ss@host:5432/db?sslmode=require"
