"""
Central application configuration. Everything that varies between a laptop demo,
a Docker Compose run, and a hosted deployment lives here and only here — no other
module should read `os.environ` directly.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "Lenny Growth Assistant"
    ENV: str = "development"
    FRONTEND_ORIGIN: str = "http://localhost:3000"  # comma-separated list of allowed origins
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password123@localhost:5432/lenny_assistant"

    # --- LLM providers ---
    DEFAULT_LLM_PROVIDER: str = "ollama"  # "ollama" | "anthropic"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # --- Embeddings ---
    EMBEDDING_PROVIDER: str = "sentence_transformers"  # "sentence_transformers" | "ollama"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSION: int = 384

    # --- RAG ---
    RETRIEVAL_TOP_K: int = 5
    # Cosine similarity floor. Confirmed via a live diagnostic against the real
    # 675-chunk corpus: raising this alone doesn't fix weak retrieval (the best
    # score for a genuinely-answerable growth-loops question was 0.37, below a
    # 0.45 floor, while the actually-relevant chunk — Mark Pincus discussing
    # feedback loops and the ASN metric — wasn't even in the top-15 nearest
    # neighbors for that query at all). The real fix is a wider candidate pool
    # before filtering (see RETRIEVAL_CANDIDATE_POOL below), not a higher floor,
    # which would only make the refusal path stricter without addressing why
    # the right chunk wasn't found in the first place. Kept at 0.35 deliberately.
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.35
    # After the absolute floor above, additionally drop any chunk scoring more
    # than this far below the single best-matching chunk — keeps a strong match
    # from being diluted by weaker also-rans that individually still clear the
    # floor. Only has an effect when there's a real gap between the best match
    # and the rest; a tightly-clustered set of scores is left untouched.
    RETRIEVAL_RELATIVE_MARGIN: float = 0.15
    # How many nearest-neighbor candidates pgvector fetches BEFORE the two
    # filtering stages above run — deliberately larger than RETRIEVAL_TOP_K.
    # The prior implementation fetched only `top_k` candidates from SQL, so a
    # relevant chunk ranked outside the top few by raw vector distance could
    # never be considered at all, no matter how the threshold/margin were
    # tuned. This widens the net first; RETRIEVAL_TOP_K still caps how many
    # chunks are ultimately returned to the LLM after filtering.
    RETRIEVAL_CANDIDATE_POOL: int = 15
    CHUNK_TARGET_TOKENS: int = 650
    CHUNK_OVERLAP_TOKENS: int = 100

    # --- Ship 30 for 30 ---
    SHIP30_TARGET_WORDS: int = 1250


@lru_cache
def get_settings() -> Settings:
    return Settings()
