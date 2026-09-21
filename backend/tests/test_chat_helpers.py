"""Unit tests for chat.py's small pure helpers — the follow-up retrieval expansion
and citation-URL filtering logic added for real-data support."""
from app.api.chat import _previous_user_message, _source_url_for
from app.providers.base import ChatMessage


def test_previous_user_message_returns_turn_before_current():
    history = [
        ChatMessage(role="user", content="how should I think about pricing?"),
        ChatMessage(role="assistant", content="here's what guests said..."),
        ChatMessage(role="user", content="what about for freemium?"),
    ]
    assert _previous_user_message(history, "what about for freemium?") == "how should I think about pricing?"


def test_previous_user_message_none_on_first_turn():
    history = [ChatMessage(role="user", content="only message")]
    assert _previous_user_message(history, "only message") is None


def test_previous_user_message_ignores_assistant_turns():
    history = [
        ChatMessage(role="assistant", content="a stray assistant-only row"),
        ChatMessage(role="user", content="first real question"),
    ]
    assert _previous_user_message(history, "first real question") is None


def test_source_url_accepts_http_urls():
    assert _source_url_for("https://www.youtube.com/watch?v=abc123&t=90s") == "https://www.youtube.com/watch?v=abc123&t=90s"


def test_source_url_rejects_local_file_paths():
    assert _source_url_for("sample_transcripts/01-plg-onboarding.md") is None


def test_source_url_handles_none():
    assert _source_url_for(None) is None
