# Architecture — The Lenny Growth Assistant

## 1. System Components

```
                        ┌─────────────────────────┐
                        │        frontend         │
                        │  Next.js (App Router)   │
                        │  Chat pane | Artifact    │
                        │  pane, SSE stream client │
                        └────────────┬─────────────┘
                                     │ HTTP / SSE (fetch)
                        ┌────────────▼─────────────┐
                        │         backend          │
                        │        FastAPI           │
                        │  ┌─────────────────────┐ │
                        │  │ api/health           │ │
                        │  │ api/sessions         │ │
                        │  │ api/chat  (SSE)      │ │
                        │  └─────────┬───────────┘ │
                        │  ┌─────────▼───────────┐ │
                        │  │ rag/retriever         │ │──► pgvector similarity search
                        │  │ rag/embeddings        │ │
                        │  │ skills/ship30_writer  │ │
                        │  │ skills/artifact_gen   │ │
                        │  │ providers/factory     │ │──► OllamaProvider / ClaudeProvider
                        │  └─────────┬───────────┘ │
                        └────────────┼─────────────┘
                                     │ asyncpg/SQLAlchemy
                        ┌────────────▼─────────────┐
                        │   PostgreSQL + pgvector   │
                        │ sessions / messages /     │
                        │ artifacts / transcript_   │
                        │ chunks (HNSW index)       │
                        └───────────────────────────┘
```

Ollama runs as its own process/container (`http://ollama:11434` in Docker, or
`http://localhost:11434` when run natively) and is called over HTTP by `OllamaProvider` — it is not a
Python dependency of the backend.

## 2. Database Schema

```sql
-- sessions
id            UUID PRIMARY KEY
title         TEXT NOT NULL DEFAULT 'New conversation'
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()

-- messages
id            UUID PRIMARY KEY
session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE
role          TEXT NOT NULL CHECK (role IN ('user','assistant','system'))
content       TEXT NOT NULL
sources       JSONB NOT NULL DEFAULT '[]'   -- [{episode, guest, timestamp, score, excerpt}]
provider      TEXT                          -- 'ollama' | 'anthropic', which one produced this reply
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

-- artifacts
id            UUID PRIMARY KEY
message_id    UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE
artifact_type TEXT NOT NULL CHECK (artifact_type IN ('markdown','html'))
title         TEXT NOT NULL DEFAULT 'Untitled artifact'
content       TEXT NOT NULL
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

-- transcript_chunks
id              UUID PRIMARY KEY
episode_title   TEXT NOT NULL
guest_name      TEXT
published_at    DATE
timestamp_ref   TEXT               -- e.g. "00:14:32" or a topic label
source_location TEXT               -- file path / URL the chunk came from
chunk_index     INT NOT NULL
chunk_text      TEXT NOT NULL
embedding       VECTOR(384)        -- all-MiniLM-L6-v2 dimension (configurable)
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()

CREATE INDEX ON transcript_chunks USING hnsw (embedding vector_cosine_ops);
```

Rationale: `sources` and provider-of-record live on the `messages` row itself (not a join) so a
session's history is fully reconstructable with a single query — important for both the UI and for
handing the transcript back to a cloud provider as conversation context.

## 3. API Contracts

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Reports DB connectivity, Ollama reachability, and whether the vector index has rows |
| POST | `/api/sessions` | Create a session, returns `{id, title, created_at}` |
| GET | `/api/sessions` | List sessions (id, title, updated_at) for the sidebar |
| GET | `/api/sessions/{id}` | Full message history + artifacts for a session |
| POST | `/api/chat` | Body: `{session_id, message, mode: 'default'|'ship30', provider: 'ollama'|'anthropic'}`. Returns `text/event-stream` of `status` / `token` / `sources` / `artifact` / `done` / `error` events |
| GET | `/api/providers` | Which providers are configured/available right now (used to disable the cloud toggle if no API key is set) |

All request bodies are validated with Pydantic v2 models (`app/models/schemas.py`); validation failures
return RFC-7807-style structured error bodies (`{"error": {"code", "message", "detail"}}`), not raw
tracebacks.

## 4. Ingestion & Retrieval Flow

```
scripts/download_transcripts.py — fetches Lenny's real public starter-pack dataset
  (github.com/LennysNewsletter/lennys-newsletterpodcastdata) directly from GitHub's
  raw content host into data/lennys_podcast/ (gitignored — see architecture §8 and
  PRD §3 for why it's never committed), or copies a local/paid archive with
  --local-source-dir. sample_transcripts/ (3 synthetic files, committed) covers
  ingestion without any network access, for tests and offline demos.
        ↓
transcript file (.md, front-matter: title/guest/date + video_id/youtube_url/
  post_url on real episodes)
   → scripts/ingest.py: parse front-matter + body
   → rag/chunking.py: recursive character splitter, ~500-800 tokens, 100-token overlap,
     preserving the nearest [HH:MM:SS] timestamp marker per chunk
   → rag/embeddings.py: EmbeddingService (sentence-transformers, or Ollama nomic-embed-text)
   → source_location resolved per chunk, in order of specificity: a YouTube deep
     link to the exact timestamp (video_id + parsed seconds) → a plain YouTube URL
     → the newsletter post URL → the local file path (synthetic fixtures only)
   → INSERT INTO transcript_chunks (... , embedding)
```

Query time:

```
user message → embed query (expanded with the previous turn if the first attempt on
  the raw message returns nothing, to handle thin follow-ups without weakening
  refusal on genuinely out-of-domain questions) → pgvector cosine similarity search,
  candidate_pool=15 nearest neighbors fetched (deliberately wider than the final
  result count — see below), three-stage relevance filter:
    stage 0 — widen before filtering: fetch candidate_pool=15 candidates from SQL,
      not just top_k=5. Confirmed necessary via a live diagnostic against the real
      675-chunk corpus: for a genuinely-answerable growth-loops question, the
      actually-relevant chunk (a guest discussing feedback loops and an engagement
      metric) wasn't even among the 5 nearest neighbors by raw vector distance —
      fetching only top_k meant the filters below could never have found it,
      regardless of how threshold/margin were tuned. This is a retrieval-recall
      fix, not a filtering-precision fix.
    stage 1 — absolute floor: similarity_threshold=0.35 (cosine similarity on
      normalized MiniLM embeddings; documented as tunable per embedding model in
      .env). Deliberately kept at 0.35 rather than raised further — the same
      diagnostic showed the best candidate for that query scored only 0.37, so a
      stricter floor would have made refusal more aggressive without addressing
      why the right chunk wasn't found in the first place)
    stage 2 — relative dominance: once a chunk clears the floor, additionally
      drop any chunk scoring more than relative_margin=0.15 below the single
      best-matching chunk, so a strong match isn't diluted by weaker also-rans
      that only individually cleared the floor (a tightly-clustered set of
      scores is left untouched — this only fires when there's a real gap)
    → final result capped at top_k=5 after stages 1/2 — the wider candidate_pool
      only gives the filters more to choose from, it never changes how many
      chunks the LLM ultimately sees
→ if best score < threshold on both attempts: return the explicit "not enough
  information" answer, no LLM call needed
→ else: build grounded system prompt with citation instructions — each excerpt is
     labeled inline with its relevance score, and the model is instructed to weigh
     higher-relevance excerpts as primary evidence rather than treating "was
     retrieved at all" as equivalent to "is actually on-topic"
     → LLMProvider.generate_response(...) (streamed)
     → citations attached to the message row as structured `sources` JSON — episode,
       guest, timestamp, similarity score, excerpt, and a clickable source_url when
       the chunk's source_location is an actual URL rather than a local file path
```

## 5. Agent / Skill Boundaries

- `rag/retriever.py` — **only** responsible for turning a query into ranked, cited chunks. No LLM calls.
- `providers/*` — **only** responsible for turning `(messages, system_prompt)` into streamed tokens for a
  given backend. No RAG logic, no prompt construction beyond what it's handed.
- `skills/ship30_writer.py` — a **pure prompt-construction module**: given retrieved chunks + a user
  request, returns the exact system/user prompt pair to send to whichever provider is active. It never
  talks to the DB or a provider directly, which is what makes it "a dedicated reusable skill" rather than
  logic embedded in the chat handler — `api/chat.py` calls it, then hands the result to the same
  `LLMProvider` used for normal chat.
- `skills/artifact_generator.py` — detects `<artifact type="..." title="...">...</artifact>` tags in a
  completed model response, extracts them into `Artifact` rows, and strips them from the chat-visible
  text so the chat pane shows a reference card instead of raw markup.
- `api/chat.py` — orchestration only: calls retriever → (chat prompt or ship30 skill) → provider →
  artifact_generator → persistence. Provider-specific branching never appears here or anywhere outside
  `providers/factory.py`.

## 6. Provider Routing

`providers/factory.py::get_provider(name: str) -> BaseLLMProvider` is the single place that knows how to
construct a provider from config/env. `api/chat.py` and `api/providers.py` only ever call the factory —
no `if provider == "ollama"` branches exist elsewhere in the app. Selection precedence: explicit
`provider` field in the chat request → `DEFAULT_LLM_PROVIDER` env var → `ollama`. If a requested provider
isn't configured (e.g., cloud key missing), the factory raises a typed `ProviderUnavailableError` that
`api/chat.py` turns into a structured SSE `error` event instead of a 500.

## 7. Trade-off: no agent framework

The assignment permits (but does not require) the Anthropic Claude Agent SDK or LangChain/LlamaIndex.
This build uses a small hand-rolled orchestration layer instead. Reasoning: at this scope (one retrieval
tool + one writing skill, no multi-step tool-calling loop), a framework adds an abstraction the evaluator
has to learn without adding capability — the explicit skill-boundary design above achieves the same
"clear skill boundaries and reliable routing" goal the rubric asks for, with less code to audit. If the
assistant grows multi-step tool use (e.g., "search, then draft, then critique"), `LangGraph` or the Claude
Agent SDK would be the first thing to reach for.

## 8. Security

- **Artifact isolation:** generated HTML is treated as fully untrusted. `SandboxedIframe` renders via
  `srcDoc` inside `<iframe sandbox="allow-scripts">` — `allow-same-origin` is never set, so the iframe has
  a unique opaque origin: no access to parent cookies, `localStorage`, DOM, or fetch calls that could hit
  authenticated app APIs. Content is additionally run through DOMPurify first, which strips `<base>`/
  `<meta http-equiv="refresh">` (redirect/URL-hijack vectors) and inline event-handler attributes on
  ordinary elements; `<script>` tags are deliberately *not* stripped (DOMPurify would remove them by
  default) because the sandbox — not the sanitizer — is what neutralizes a script's capabilities, and
  blocking `<script>` would silently break every interactive HTML artifact. Verified by a dedicated test
  suite (`frontend/src/components/Artifact/__tests__/SandboxedIframe.test.tsx`).
- **Data licensing:** the real transcript dataset (§4) is downloaded at run time into a gitignored
  directory rather than committed, per its license's no-redistribution term — see PRD §3.
- **Secrets:** all API keys come from environment variables, never committed; `.env.example` ships with
  placeholders only; structured logs redact any field named `*_key`/`*_token`/`*_password`.
- **Injection:** all DB access uses parameterized queries (SQLAlchemy / asyncpg bind params) — the raw-SQL
  similarity query uses bound parameters for the vector and thresholds, never string interpolation.
- **CORS:** restricted to the configured frontend origin (`FRONTEND_ORIGIN` env var), not `*`.

## 9. Deployment Topology

Local/demo: `docker-compose.yml` runs `db` (Postgres 16 + pgvector), `backend` (FastAPI/uvicorn),
`frontend` (Next.js). Ollama runs natively on the host (recommended, for GPU/Metal access) or as an
optional `ollama` service — the model itself is pulled once via `docker exec lenny_ollama ollama pull
llama3.2:3b`, deliberately **not** baked into `docker compose up`, per the assignment's own guidance that
auto-pulling a multi-GB model at startup makes evaluation unreliable.

Production (documented, not deployed for this submission): Postgres → Supabase/Railway managed pgvector;
backend → any container host with the same image; frontend → Vercel/static export behind the same API
origin; Ollama would typically be replaced by cloud-only in a hosted environment unless a GPU node is
available.
