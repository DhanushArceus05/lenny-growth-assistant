"""Cloud provider — Anthropic Claude. Same streaming contract as OllamaProvider so
api/chat.py never needs to know which one it's talking to."""
from collections.abc import AsyncIterator

from app.providers.base import BaseLLMProvider, ChatMessage, ProviderTimeoutError, ProviderUnavailableError


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model
        self._client = None
        if api_key:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def check_available(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "ANTHROPIC_API_KEY is not set"
        return True, None

    async def generate_response(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        if not self._client:
            raise ProviderUnavailableError(self.name, "ANTHROPIC_API_KEY is not set")

        import anthropic

        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": m.role, "content": m.content} for m in messages],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError(self.name) from exc
        except anthropic.AuthenticationError as exc:
            raise ProviderUnavailableError(self.name, "invalid API key") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderUnavailableError(self.name, f"API error {exc.status_code}") from exc
