"""API-level validation for the chat endpoint's critical-path input. Full streaming
chat orchestration requires a live Postgres+pgvector+Ollama stack and is covered by
the manual test plan in README.md instead of a fragile end-to-end unit test."""
import pytest
from pydantic import ValidationError

from app.models.schemas import ChatRequest


def test_blank_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(session_id="abc", message="   ")


def test_valid_chat_request_defaults_to_default_mode():
    req = ChatRequest(session_id="abc", message="What did guests say about pricing?")
    assert req.mode == "default"
    assert req.provider is None


def test_ship30_mode_accepted():
    req = ChatRequest(session_id="abc", message="Write a Ship 30 essay on onboarding", mode="ship30")
    assert req.mode == "ship30"


async def test_chat_against_missing_session_returns_error_event(client):
    resp = await client.post("/api/chat", json={"session_id": "does-not-exist", "message": "hello"})
    assert resp.status_code == 200
    assert "not_found" in resp.text
