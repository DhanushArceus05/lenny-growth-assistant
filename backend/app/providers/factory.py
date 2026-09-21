"""The one place in the app that maps a provider name to a concrete instance.
Every route that needs a provider goes through get_provider() — no other module
should import OllamaProvider/AnthropicProvider directly."""
from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.base import BaseLLMProvider
from app.providers.cloud_provider import AnthropicProvider
from app.providers.ollama_provider import OllamaProvider

PROVIDER_NAMES = ("ollama", "anthropic")


def _build(name: str, settings: Settings) -> BaseLLMProvider:
    if name == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            timeout_seconds=settings.OLLAMA_TIMEOUT_SECONDS,
        )
    if name == "anthropic":
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    raise ValueError(f"unknown provider '{name}'")


@lru_cache
def get_provider(name: str | None = None) -> BaseLLMProvider:
    settings = get_settings()
    resolved = name or settings.DEFAULT_LLM_PROVIDER
    if resolved not in PROVIDER_NAMES:
        resolved = settings.DEFAULT_LLM_PROVIDER
    return _build(resolved, settings)


async def list_provider_status(settings: Settings | None = None):
    from app.models.schemas import ProviderStatus

    settings = settings or get_settings()
    statuses = []
    for name in PROVIDER_NAMES:
        provider = _build(name, settings)
        available, reason = await provider.check_available()
        statuses.append(ProviderStatus(name=name, available=available, reason=reason))
    return statuses
