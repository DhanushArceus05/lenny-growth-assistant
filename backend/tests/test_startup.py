"""
Regression test for the exact bug found during local Docker verification:
`init_models()` existed in database.py but was never called anywhere, so
sessions/messages/artifacts were never created on a fresh database — GET
/api/sessions failed with `UndefinedTableError` even though transcript_chunks
(created separately by scripts/ingest.py) was already populated.

This uses Starlette's TestClient as a context manager specifically because that's
what actually triggers ASGI lifespan startup/shutdown events — the AsyncClient +
ASGITransport pattern used in conftest.py's `client` fixture does NOT trigger
lifespan, which is exactly how this bug went unnoticed by the existing test suite.
"""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_calls_init_models_on_startup():
    with patch("app.main.init_models", new_callable=AsyncMock) as mock_init:
        with TestClient(app):
            pass  # entering/exiting the context triggers startup/shutdown
    mock_init.assert_awaited_once()


def test_startup_does_not_crash_app_if_db_init_fails():
    """A DB that's briefly unreachable at startup must not take the whole app
    down — /api/health should still be able to report the failure instead of
    uvicorn refusing to start."""
    with patch("app.main.init_models", new_callable=AsyncMock) as mock_init:
        mock_init.side_effect = Exception("connection refused")
        with TestClient(app) as client:
            # The app must still be usable after a failed init — hitting a route
            # that doesn't touch the DB proves the process is alive and serving.
            resp = client.get("/")
            assert resp.status_code == 200


def test_cors_allow_origins_splits_comma_separated_frontend_origin():
    """Regression test for the exact bug found during live Docker verification:
    a single hardcoded FRONTEND_ORIGIN silently didn't match the browser's actual
    origin when the frontend ran on a non-default port. CORS now accepts a
    comma-separated list so multiple valid origins (e.g. :3000 default and a
    locally remapped :3002) can be allowed simultaneously."""
    from starlette.middleware.cors import CORSMiddleware

    cors_middleware = next(
        m for m in app.user_middleware if m.cls is CORSMiddleware
    )
    allowed = cors_middleware.kwargs["allow_origins"]
    assert "http://localhost:3000" in allowed or "http://localhost:3002" in allowed
    assert all(o == o.strip() and o for o in allowed)
