# The Lenny Growth Assistant

A full-stack, retrieval-augmented assistant that answers product/growth questions
strictly from Lenny's Podcast transcripts, turns answers into Ship 30 for 30-style
essays, and renders generated Markdown/HTML as artifacts beside the chat — built for
the Oogway Labs Forward Deployed Engineer take-home assignment.

**Read this first:** this README explicitly separates what was **verified in the
build environment** from what is **implemented but requires your local
Docker/Postgres/Ollama to verify end-to-end** — see §11.

## 1. What it does

- Ask a product/growth question → the assistant retrieves the most relevant
  transcript excerpts via pgvector similarity search, answers **only** from those
  excerpts, cites the guest/episode/timestamp, and explicitly says so if nothing in
  the archive is relevant enough — it does not guess.
- Ask for a "Ship 30 for 30" essay on a topic → a dedicated skill turns the same
  grounded context into a ~1,250-word, headline/hook/bullets-structured essay,
  rendered as a Markdown artifact.
- Ask for an HTML one-pager/snippet → rendered live in a sandboxed iframe next to
  the chat, isolated from the rest of the app (see §9).
- Switch between a local Ollama model and Anthropic Claude from the UI, with no
  code changes.

## 2. Architecture at a glance

```
Next.js (chat + artifact pane) → FastAPI (SSE) → retriever (pgvector) → skill (grounded chat / ship30) → provider (Ollama | Anthropic)
                                        ↓
                              PostgreSQL (sessions, messages, artifacts, transcript_chunks)
```

Full detail, database schema, API contracts, and the "why no agent framework"
trade-off: [`docs/architecture.md`](docs/architecture.md). Product framing, success
metrics, assumptions, and scope: [`docs/PRD.md`](docs/PRD.md). UI/UX principles:
[`docs/design.md`](docs/design.md).

## 3. Project structure

```
lenny-growth-assistant/
├── docs/                    PRD, architecture, design
├── agent_transcripts/       coding-agent session logs (see its own README)
├── backend/
│   ├── app/
│   │   ├── api/             health, sessions, chat (SSE), providers
│   │   ├── providers/       Ollama + Anthropic behind one interface
│   │   ├── rag/             chunking, embeddings, retriever
│   │   ├── skills/          ship30_writer, grounded_chat, artifact_generator
│   │   └── models/          SQLAlchemy models + Pydantic schemas
│   ├── scripts/
│   │   ├── ingest.py               real ingestion pipeline (chunk → embed → pgvector)
│   │   └── download_transcripts.py transcript-loader stub — see §6
│   ├── sample_transcripts/  synthetic demo/test fixtures (NOT real Lenny's data — §6)
│   └── tests/               28 pytest tests
├── frontend/
│   └── src/                 Next.js App Router, Tailwind, chat + artifact components
├── docker-compose.yml
└── .env.example
```

## 4. Prerequisites

- Docker & Docker Compose v24+ (for the one-command path), **or** Python 3.11+ and
  Node.js 18/20 for local dev without Docker.
- [Ollama](https://ollama.com) installed — mandatory for the demo per the
  assignment. Either run it natively on your host, or use the `ollama` container in
  `docker-compose.yml`.
- (Optional) an Anthropic API key, if you want the cloud provider available.

## 5. Quick start (Docker)

```bash
cp .env.example .env          # fill in ANTHROPIC_API_KEY if you want the cloud provider
docker compose up --build
```

This starts `db` (Postgres 16 + pgvector), `ollama`, `backend` (FastAPI on :8000),
and `frontend` (Next.js on :3000).

**Pull the local model once** (deliberately not done automatically at startup — see
`docker-compose.yml`'s top comment for why):

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

**Download and ingest the real transcript data** (also not automatic — these are
data-loading steps, not app-startup steps):

```bash
docker compose exec backend python -m scripts.download_transcripts --limit 15
docker compose exec backend python -m scripts.ingest --source-dir data/lennys_podcast
```

(Drop `--limit 15` to fetch the full ~50-episode free starter pack. See §6 for what
this actually downloads and why.)

Then open **http://localhost:3000**.

If you'd rather run Ollama natively (recommended for GPU/Apple Silicon
acceleration instead of the CPU-only container), stop the `ollama` service and set
`OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env`.

## 6. Transcript data — important

The assignment asks for "the public Lenny's Podcast transcript repository." That
repository exists and is identifiable: Lenny Rachitsky's own official public
starter pack —
[`LennysNewsletter/lennys-newsletterpodcastdata`](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata)
— 50 free real episode transcripts with front-matter (title, guest, date, and on
many episodes a YouTube video ID) and real `(HH:MM:SS)`-stamped speaker turns.

**`scripts/download_transcripts.py` downloads this real dataset directly** from
GitHub's raw content host — no synthetic substitute:

```bash
cd backend
python -m scripts.download_transcripts            # all ~50 free episodes
python -m scripts.download_transcripts --limit 10  # just a handful, for a quick test
```

**Why the downloaded files aren't in this repo:** the dataset's `LICENSE.md`
permits personal, non-commercial use and publishing projects built with it (this
project qualifies), but explicitly **prohibits redistributing the raw dataset
files**. So the script downloads into `backend/data/lennys_podcast/`, which this
project's `.gitignore` excludes — you run the download yourself; it's never
bundled into the submitted repository. The full license text is saved alongside
the downloaded files (`data/lennys_podcast/LICENSE.md`) so it's easy to check.

Then ingest it:

```bash
python -m scripts.ingest --source-dir data/lennys_podcast
```

Citations built from this real data include a clickable source link — a YouTube
deep link to the exact timestamp when the episode's front-matter has a video ID,
falling back to the newsletter post URL otherwise.

**Three synthetic, clearly-labeled sample transcripts** remain in
`backend/sample_transcripts/` (committed, since they're written for this project,
not scraped) purely as a no-network fallback — used by the automated test suite
and for a quick demo if you can't reach GitHub:

```bash
python -m scripts.ingest --source-dir sample_transcripts
```

If you have access to the paid full archive at lennysdata.com (or your own
licensed export) already on disk, point the downloader at it instead of fetching
the free pack:

```bash
python -m scripts.download_transcripts --local-source-dir /path/to/your/archive
```

Real transcript files follow this front-matter shape (also documented in
`scripts/ingest.py`):
```markdown
---
title: "Episode title"
guest: "Guest Name"
date: "2026-05-01"
video_id: "abc123XYZ"        # optional — enables exact-timestamp citation links
youtube_url: "https://www.youtube.com/watch?v=abc123XYZ"   # optional
post_url: "https://www.lennysnewsletter.com/p/..."          # optional fallback link
---
**Guest Name** (00:02:10):
transcript text — (HH:MM:SS) timestamps anywhere in the body are picked up per chunk.
```

## 7. Environment variables

See [`.env.example`](.env.example) for the full list with safe defaults. Key ones:

| Variable | Purpose |
|---|---|
| `DEFAULT_LLM_PROVIDER` | `ollama` (default, no key needed) or `anthropic` |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | where Ollama is running and which model to use |
| `ANTHROPIC_API_KEY` | leave blank to disable the cloud provider (UI shows it as unavailable, doesn't error) |
| `EMBEDDING_PROVIDER` | `sentence_transformers` (default, runs in-process) or `ollama` (uses `nomic-embed-text`) |
| `RETRIEVAL_SIMILARITY_THRESHOLD` | how strict the grounded/refusal boundary is (0–1, cosine similarity) |
| `RETRIEVAL_CANDIDATE_POOL` | how many nearest-neighbor candidates are fetched before filtering — wider than `RETRIEVAL_TOP_K`, which still caps the final result count |

**Never commit a real `.env`** — it's gitignored; `.env.example` contains only
placeholders.

## 8. Local development (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit DATABASE_URL to point at your local Postgres
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000, expects the backend on :8000
```

## 9. Artifact security model

Generated HTML is treated as fully untrusted. The viewer (`SandboxedIframe.tsx`):

- Renders via **`srcDoc`**, never a `src` pointing at the app's own origin.
- Sets **`sandbox="allow-scripts"`** and deliberately never adds
  `allow-same-origin` — this gives the iframe a unique opaque origin, so even a
  malicious script inside an artifact cannot read this app's cookies,
  `localStorage`, DOM, or make same-origin requests to authenticated APIs.
- Runs content through **DOMPurify** first as a second, independent layer — it
  strips `<base>`/`<meta http-equiv="refresh">` (URL-hijack/redirect vectors) and
  inline event-handler attributes (`onerror`, etc.) on ordinary elements.
  `<script>` tags themselves are intentionally *not* stripped by DOMPurify (they'd
  otherwise be removed by its default config) — the sandbox is what neutralizes a
  script's capabilities, not the sanitizer, and stripping `<script>` would silently
  break every interactive artifact.
- Has no `allow-top-navigation`, `allow-popups`, or `allow-forms` — an artifact
  can't navigate the parent tab, open popups, or submit a form anywhere.

Verified with a focused test suite: `frontend/src/components/Artifact/__tests__/SandboxedIframe.test.tsx`
(`npm test` in `frontend/`) — asserts the sandbox attribute, `srcDoc` usage, and
that adversarial content (fake `<base>`/`<meta>` redirects, `onerror` handlers, an
artifact attempting to smuggle its own `allow-same-origin` sandbox string) is
neutralized.

## 10. Tests

Backend (45 tests, all passing in this build — see §11):
```bash
cd backend
pip install -r requirements.txt
pytest
```
Covers: health, session CRUD, provider routing + typed failure handling (missing
key, unreachable Ollama, timeout), retrieval threshold/refusal logic, follow-up
retrieval-expansion, citation-URL filtering, real-data date parsing and
source-location fallback chain, timestamp-to-seconds conversion, Ship30 prompt
construction, artifact tag extraction, chunking overlap/timestamp behavior.
`transcript_chunks` uses pgvector-specific SQL and isn't sqlite-portable, so
retrieval is tested at the unit level against a mocked DB session — true
end-to-end pgvector search needs a live Postgres (§11).

Frontend (5 tests):
```bash
cd frontend
npm install
npm test
```

### Manual UI test plan

1. Open the app → empty state shows topic suggestions drawn from the sample data.
2. Ask a question covered by whichever data you ingested — `sample_transcripts/`
   for a no-network smoke test (e.g. "how should I think about onboarding for a
   PLG product?"), or a topic from a real downloaded episode — → expect a
   streamed, cited answer with source cards you can expand.
3. Ask something unrelated (e.g. "what's a good CRM for a 5-person sales team?") →
   expect the explicit "I don't have enough information..." response, styled as a
   neutral state, not an error.
4. Ask a follow-up that only makes sense with the prior turn's context (e.g. first
   "how should I think about pricing?", then "what about for a freemium model
   specifically?") → the follow-up should still retrieve relevant sources instead
   of refusing, and the answer should read as a continuation, not a restart.
5. If you ingested real data with a video ID, expand a source citation and click
   "Open source" → should open a YouTube link at the cited timestamp.
6. Switch the provider toggle to Claude (requires `ANTHROPIC_API_KEY` set) and ask
   again → the assistant-message badge should show `anthropic`.
7. Stop Ollama (or point `OLLAMA_BASE_URL` at a bad port) and ask while Ollama is
   selected → expect an inline, specific error with a "Switch to Claude" action,
   not a blank screen or raw stack trace.
8. Switch to "Ship 30 for 30" mode and ask for an essay on a covered topic →
   expect the artifact pane to auto-open with a ~1,250-word Markdown essay.
9. Ask the assistant to produce an HTML one-pager → expect it to render inside the
   sandboxed iframe (inspect via devtools that `sandbox="allow-scripts"` only).
10. Resize to a narrow/mobile viewport → sidebar collapses behind a menu icon,
    artifact pane becomes a full-screen sheet reachable from a message's artifact
    chip rather than squeezing three columns onto one screen.
11. Kill the `db` container mid-session → `/api/health` and the UI's connection
    indicator should reflect it without the app crashing.

## 11. What's verified vs. what needs local verification

**Verified in the build environment** (sandboxed container — no Docker daemon, no
GPU, no live Postgres/Ollama there, but outbound HTTPS to GitHub *was* available):
- 45/45 backend `pytest` tests passing (see §10 for what they cover).
- 5/5 frontend `vitest` security tests passing.
- Frontend: `tsc --noEmit` clean, `next build` production build succeeds, `next lint`
  passes (runs as part of `next build`).
- **`scripts/download_transcripts.py` actually run against the live GitHub
  dataset** — real episodes downloaded and their real front-matter/timestamp
  format parsed correctly by `scripts/ingest.py`'s helpers (verified directly, not
  just unit-tested): the YouTube-deep-link, plain-YouTube-URL, and
  newsletter-post-URL citation fallbacks were each exercised against real
  downloaded files and produced correct results.
- `ship30_writer.build_ship30_prompt` and `grounded_chat.build_grounded_prompt`
  run directly against real downloaded transcript content (not just synthetic
  fixtures) and produce correctly-grounded, correctly-attributed prompts.
- All backend modules import/parse cleanly; async ORM relationship loading
  (`selectinload`) confirmed via the sessions test.

**Implemented but requires your local Docker/Postgres/Ollama to verify
end-to-end** (not runnable in the build sandbox — no Docker daemon, no GPU, no
live Postgres/pgvector):
- `docker compose up --build` bringing up all services together.
- `scripts/ingest.py`'s actual `INSERT`s against a live Postgres+pgvector instance
  (schema/HNSW-index creation and embedding writes — the parsing/chunking/
  citation-building steps upstream of the DB write were verified directly, per
  above).
- Real pgvector cosine-similarity retrieval quality/threshold tuning against
  ingested data.
- Ollama end-to-end generation (the provider code is complete and unit-tested for
  its failure paths, but no live model call has been made).
- The full SSE chat round-trip against a real database, including the follow-up
  retrieval-expansion behavior (unit-tested piece by piece: retrieval, prompt
  construction, artifact extraction, persistence — but not exercised together
  against a live stack).
- First-token latency and the `<4s` target metric.
- The 2–3 minute demo video (not applicable to this environment).

## 12. Known limitations

- No auth/multi-tenancy — single-user demo scope, by design (see PRD §4).
- OpenAI provider not implemented (the interface supports adding one; only
  Anthropic + Ollama ship in this pass).
- Embedding model download (`sentence-transformers` weights, or Ollama's
  `nomic-embed-text`) requires internet access on first run — not bundled into the
  image to keep it a reasonable size.
- `RETRIEVAL_SIMILARITY_THRESHOLD` (default `0.35`), `RETRIEVAL_RELATIVE_MARGIN`
  (default `0.15`), and `RETRIEVAL_CANDIDATE_POOL` (default `15`) are starting
  points validated against one live diagnostic on the real corpus (see
  `agent_transcripts/`), not exhaustively tuned — expect to retune them against
  broader real usage. A weak local model (e.g. `llama3.2:1b`) is more prone to
  stretching a moderate-relevance excerpt into an answer than a larger model, so
  if you're running a small model, keep an eye on this in practice.
- The follow-up retrieval fallback (README §10/architecture.md §4) folds in only
  the single previous user turn, not a full conversation summary — good enough for
  the common one-step-back follow-up, but a multi-turn topic drift could still
  need a rephrased question.
- Only the free 50-episode starter pack is integrated; the paid full archive at
  lennysdata.com isn't, though `--local-source-dir` supports it if you have access.

## 13. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `/api/health` shows `database: false` | Postgres isn't up yet or `DATABASE_URL` is wrong — check `docker compose logs db` |
| Chat immediately errors "ollama is unavailable" | Ollama isn't running, or the model hasn't been pulled — run the `ollama pull` command in §5 |
| Every answer is a refusal | `transcript_chunks` is empty — run `scripts/ingest.py` (§5/§6) |
| Cloud provider greyed out in the UI | `ANTHROPIC_API_KEY` isn't set in `.env` — this is intentional, not a bug |
| Frontend can't reach the backend | Check `NEXT_PUBLIC_API_URL` matches where the backend is actually listening, and `FRONTEND_ORIGIN` on the backend matches where the frontend is served from (CORS) |
| `docker compose up` builds are slow the first time | `sentence-transformers`/`torch` are large; subsequent builds are cached |
| `GET /api/sessions` fails with `UndefinedTableError: relation "sessions" does not exist` | Fixed in this build — the backend now creates `sessions`/`messages`/`artifacts` on startup via a FastAPI lifespan hook. If you still see this, you're on an older image; rebuild the backend container |
| `POST /api/sessions` fails with `asyncpg.exceptions.DataError: ... can't subtract offset-naive and offset-aware datetimes` | Fixed in this build — timestamps are now generated as naive UTC datetimes to match the `TIMESTAMP WITHOUT TIME ZONE` columns. Rebuild the backend container if you still see this |
| New conversation fails with a generic "Couldn't create a new conversation" in the browser | Almost always CORS — confirm `FRONTEND_ORIGIN` (backend) actually includes the origin the browser is loading from; it's a comma-separated list, and `docker-compose.yml` always includes `:3002` as a fallback in addition to whatever `FRONTEND_PORT` resolves to |
| A port (3000/8000) is already used by another local project | Set `FRONTEND_PORT`/`BACKEND_PORT` in `.env` (see `.env.example`) — `docker-compose.yml` derives CORS/API-URL from the same variables, so you don't need to change anything else |
