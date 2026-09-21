"""
The single contract every LLM backend must satisfy. Nothing outside `providers/`
should know whether it's talking to Ollama or a cloud API — everything goes through
this interface + the factory in providers/factory.py.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


class ProviderUnavailableError(Exception):
    """Raised when a provider can't currently serve requests (missing key, unreachable
    host, etc). Callers turn this into a structured error event, never a 500."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider} unavailable: {reason}")


class ProviderTimeoutError(Exception):
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"{provider} timed out")


class BaseLLMProvider(ABC):
    name: str

    @abstractmethod
    async def check_available(self) -> tuple[bool, str | None]:
        """Cheap readiness check. Returns (available, reason_if_not)."""
        ...

    @abstractmethod
    async def generate_response(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        """Stream response text chunks. Must raise ProviderUnavailableError /
        ProviderTimeoutError rather than letting transport exceptions leak out."""
        ...
        yield ""  # pragma: no cover - abstract generator shape marker
