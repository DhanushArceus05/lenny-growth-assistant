"""Provider routing + graceful-failure behavior — one of the assignment's explicit
highest-risk paths ('missing API key', 'Ollama unavailable', 'timeout')."""
from unittest.mock import patch

import httpx
import pytest

from app.providers.cloud_provider import AnthropicProvider
from app.providers.factory import get_provider
from app.providers.ollama_provider import OllamaProvider


def test_factory_returns_correct_provider_types():
    get_provider.cache_clear()
    assert isinstance(get_provider("ollama"), OllamaProvider)
    get_provider.cache_clear()
    assert isinstance(get_provider("anthropic"), AnthropicProvider)


def test_factory_falls_back_to_default_for_unknown_name():
    get_provider.cache_clear()
    provider = get_provider("not-a-real-provider")
    assert provider.name in ("ollama", "anthropic")


async def test_anthropic_provider_unavailable_without_key():
    provider = AnthropicProvider(api_key=None, model="claude-3-5-sonnet-20241022")
    available, reason = await provider.check_available()
    assert available is False
    assert "ANTHROPIC_API_KEY" in reason


async def test_ollama_check_available_reports_connect_error():
    provider = OllamaProvider(base_url="http://localhost:19999", model="llama3.2:3b")
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")):
        available, reason = await provider.check_available()
    assert available is False
    assert "not reachable" in reason


async def test_ollama_generate_raises_typed_error_on_connect_failure():
    from app.providers.base import ProviderUnavailableError

    provider = OllamaProvider(base_url="http://localhost:19999", model="llama3.2:3b")

    class _FakeStreamCM:
        async def __aenter__(self):
            raise httpx.ConnectError("refused")

        async def __aexit__(self, *a):
            return False

    with patch("httpx.AsyncClient.stream", return_value=_FakeStreamCM()):
        with pytest.raises(ProviderUnavailableError):
            async for _ in provider.generate_response([], "system prompt"):
                pass
