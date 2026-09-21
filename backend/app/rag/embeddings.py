"""
Embedding service abstraction — sentence-transformers runs in-process (no external
call, works offline once the model is cached); Ollama's nomic-embed-text is the
alternative for an all-local, single-runtime setup. Selected via EMBEDDING_PROVIDER.
"""
from app.config import Settings, get_settings


class EmbeddingService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._st_model = None  # lazy-loaded

    async def embed(self, text: str) -> list[float]:
        if self.settings.EMBEDDING_PROVIDER == "ollama":
            return await self._embed_ollama(text)
        return self._embed_sentence_transformers(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.settings.EMBEDDING_PROVIDER == "ollama":
            return [await self._embed_ollama(t) for t in texts]
        model = self._get_st_model()
        return model.encode(texts, normalize_embeddings=True).tolist()

    def _get_st_model(self):
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self.settings.EMBEDDING_MODEL)
        return self._st_model

    def _embed_sentence_transformers(self, text: str) -> list[float]:
        model = self._get_st_model()
        return model.encode([text], normalize_embeddings=True)[0].tolist()

    async def _embed_ollama(self, text: str) -> list[float]:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.settings.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": self.settings.OLLAMA_EMBEDDING_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
