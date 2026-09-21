"""Local model provider — mandatory for the demo. Talks to a running Ollama server
over HTTP; has no other dependency on Ollama being installed in this process."""
from collections.abc import AsyncIterator

import httpx

from app.providers.base import BaseLLMProvider, ChatMessage, ProviderTimeoutError, ProviderUnavailableError


class OllamaProvider(BaseLLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def check_available(self) -> tuple[bool, str | None]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False, f"Ollama returned HTTP {resp.status_code}"
                tags = [m.get("name", "") for m in resp.json().get("models", [])]
                if tags and not any(self.model.split(":")[0] in t for t in tags):
                    return False, f"model '{self.model}' not pulled (run: ollama pull {self.model})"
                return True, None
        except httpx.ConnectError:
            return False, f"Ollama not reachable at {self.base_url} — is it running?"
        except Exception as exc:  # noqa: BLE001 - readiness check must never raise
            return False, str(exc)

    async def generate_response(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}]
            + [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise ProviderUnavailableError(self.name, f"HTTP {response.status_code}: {body[:200]!r}")
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        import json

                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise ProviderUnavailableError(self.name, chunk["error"])
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            return
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(self.name, f"not reachable at {self.base_url}") from exc
        except httpx.ReadTimeout as exc:
            raise ProviderTimeoutError(self.name) from exc
