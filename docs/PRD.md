# PRD — The Lenny Growth Assistant

## 1. Persona & Problem

**Primary persona:** A Growth PM or early-career product manager who follows Lenny's Podcast but doesn't
have time to listen to 200+ hours of episodes. They want a specific, tactical answer ("how do I structure
a PLG onboarding flow?", "what did guests say about pricing experiments?") backed by a real source, not a
generic LLM guess.

**Job to be done:** "When I have a live product/growth decision to make, I want to pull a grounded,
citable answer from the collective knowledge of Lenny's guests in under a minute, and turn it into a
shareable write-up without doing the writing myself."

**Pain removed:** Hours of manual transcript search/skimming, uncertainty about whether an AI answer is
actually grounded in something a real practitioner said, and the separate step of turning research into
publishable content.

## 2. Success Metrics

These are **target metrics**, not measured results — flagged explicitly per the assignment brief and
re-validated once real usage/eval data exists:

| Metric | Target | How it's checked |
|---|---|---|
| Retrieval citation accuracy | ≥ 90% of grounded answers cite a chunk that actually supports the claim | Manual spot-check + `test_retrieval.py` relevance-threshold tests |
| Local model first-token latency | < 4s on a 16GB-RAM machine with a 3B–8B Ollama model | Manual timing during demo |
| Artifact rendering safety | 0 known XSS vectors in the sandboxed viewer | `SandboxedIframe` sandbox flags + DOMPurify + manual test plan |
| Grounded refusal | Assistant explicitly declines to answer when similarity scores fall below threshold, instead of hallucinating | `test_retrieval.py::test_low_relevance_triggers_refusal` |

## 3. Assumptions (brief was incomplete)

- **Transcript source — resolved with the real public dataset:** The assignment references "the public
  Lenny's Podcast transcript repository" without naming one. That repository exists and is identifiable:
  Lenny Rachitsky's own official public starter pack,
  [`LennysNewsletter/lennys-newsletterpodcastdata`](https://github.com/LennysNewsletter/lennys-newsletterpodcastdata)
  (50 free real episode transcripts with title/guest/date front-matter, real `[HH:MM:SS]`-stamped speaker
  turns, and — on many episodes — a YouTube video ID for exact-moment citation links). `scripts/
  download_transcripts.py` downloads this real dataset directly from GitHub's raw content host. Its
  `LICENSE.md` permits personal, non-commercial use and publishing projects built with it, but explicitly
  prohibits redistributing the raw dataset files — so the downloaded transcripts live in
  `backend/data/lennys_podcast/`, which is gitignored, not bundled into this repository. Anyone running
  this project runs the download script themselves (documented in README §6). Three small, clearly-labeled
  **synthetic** transcripts remain in `backend/sample_transcripts/` purely as no-network test/demo fixtures
  (used by the automated test suite and as a fallback if someone can't reach GitHub).
- **Agent framework:** The official assignment allows FastAPI + "Anthropic Claude Agent SDK, Pi Coding
  Agent, or LangChain/LlamaIndex primitives." We implement a **hand-rolled retrieval + provider
  abstraction** rather than pulling in a heavy agent framework — this satisfies "clear skill boundaries
  and reliable routing" without adding a dependency whose behavior is opaque to the evaluator. This is
  documented as a deliberate trade-off (see architecture.md §7).
- **Cloud provider:** Anthropic Claude is the default cloud provider (matches the assignment's own
  authorship and the spec doc's first-listed option); OpenAI is not implemented in this pass — the
  provider interface is designed so adding it is a single new file.
- **Auth:** No user auth/multi-tenant accounts — out of scope for a take-home demo. Sessions are
  identified by UUID only.
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` is the default local embedding model (also
  configurable to Ollama's `nomic-embed-text`), matching the spec doc.
- **Hosting:** Local-first via Docker Compose. Supabase/Railway hosting is documented but not deployed as
  part of this submission (time-boxed, and the assignment's mandatory demo path is local Ollama anyway).

## 4. Scope

**In scope (P0/P1):**
- FastAPI backend, PostgreSQL + pgvector, transcript ingestion/chunking/embedding pipeline
- Grounded RAG chat with source citations and explicit "not enough information" refusal
- Session + message + artifact persistence
- Ollama provider (mandatory) + Anthropic cloud provider, switchable via config/UI without code changes
- Ship 30 for 30 skill as a dedicated, reusable module (not an inline prompt)
- Markdown + HTML/CSS artifact generation with a sandboxed, security-documented viewer
- Structured logging, graceful failure handling (DB down, Ollama down, missing key, timeout, empty
  retrieval, malformed output)
- Docker Compose one-command startup (Ollama model pull documented separately, not baked into `up`)
- Automated tests for the highest-risk paths + manual UI test plan
- README / PRD / architecture / design docs, agent transcripts folder

**Explicitly out of scope:**
- User accounts/auth, multi-tenant billing, RBAC
- OpenAI provider (interface supports it; not implemented this pass)
- Fine-tuning, evaluation harness/dashboards beyond the target-metric table above
- Production hosting/CI-CD pipeline
- Bundling the full paid transcript archive — the free 50-episode starter pack (downloaded at run time,
  not committed — see Assumptions) is what ships with this build

## 5. User Flows

1. **New session → grounded question:** User opens app → new session created → asks a product/growth
   question → backend retrieves top-K chunks → if above threshold, streams a grounded answer with source
   cards (linking to the exact YouTube moment when the source transcript has a video ID); if below
   threshold, explicitly says the archive doesn't have enough information.
2. **Follow-up in same session:** User asks a follow-up → prior turns are included as conversation
   context for both the LLM prompt and retrieval itself — a thin follow-up that retrieves nothing on its
   own is retried once with the previous turn folded into the query before falling back to refusal.
3. **Ship 30 for 30 request:** User asks the assistant to turn the last grounded answer (or a topic) into
   a Ship 30 essay → dedicated skill runs against the same retrieved chunks → returns a ~1,250-word
   Markdown artifact → artifact pane opens automatically.
4. **HTML artifact request:** User asks for a rendered snippet (e.g., a one-pager) → backend returns an
   `artifact_type=html` payload → frontend mounts it in a sandboxed iframe via `srcDoc`, sanitized with
   DOMPurify.
5. **Provider switch:** User toggles Ollama ↔ Claude in the UI (or sets `DEFAULT_PROVIDER` in `.env`) →
   next message routes through the new provider with no code change.
6. **Failure states:** Ollama down → chat shows a clear inline error and suggests switching provider; DB
   down → health endpoint and UI both surface it; cloud key missing → cloud option is disabled in the UI
   with a tooltip rather than failing silently at request time.

## 6. Acceptance Criteria

- [ ] `docker compose up --build` brings up `db`, `backend`, `frontend` (Ollama documented as a separate
      one-time pull, per the assignment's own guidance on not making startup fragile).
- [ ] Running `backend/scripts/download_transcripts.py` then `backend/scripts/ingest.py --source-dir
      data/lennys_podcast` populates `transcript_chunks` with real episode data (or `--source-dir
      sample_transcripts` for the no-network synthetic fixtures).
- [ ] A grounded question returns an answer with ≥1 source citation traceable to episode/guest, with a
      clickable YouTube/newsletter link when the source transcript provides one.
- [ ] An out-of-domain question triggers the explicit refusal message, not a hallucinated answer.
- [ ] Switching provider in the UI changes which backend actually serves the next message.
- [ ] A Ship 30 request returns a Markdown artifact rendered in the artifact pane.
- [ ] An HTML artifact request renders inside a sandboxed iframe with no `allow-same-origin`.
- [ ] `pytest` passes for health, provider-routing, retrieval-threshold, and artifact-handling tests.
- [ ] Killing the DB/Ollama container produces a graceful, logged error, not a 500 with a stack trace.

## 7. Risks & Trade-offs

| Risk | Mitigation |
|---|---|
| Hallucination when context is thin | Hard similarity threshold + explicit refusal instruction in system prompt |
| Local model reasoning quality vs. cloud | Documented as a known trade-off; UI clearly badges which provider answered |
| Unsafe HTML artifacts (XSS) | `sandbox="allow-scripts"` **without** `allow-same-origin`, `srcDoc` (not same-origin src), DOMPurify pre-sanitization, no artifact ever gets fetch/cookie/localStorage access |
| Data leakage via cloud provider | Only retrieved transcript chunks + user message are sent to the cloud provider; no session history beyond the current conversation is persisted server-side beyond Postgres, which the client controls |
| Latency (local model) | Streaming responses so perceived latency is lower than time-to-completion; target <4s first token documented, not guaranteed on all hardware |
| Licensing on real transcript data | Uses Lenny's own official free starter dataset via a real downloader; the dataset's no-redistribution term is respected by gitignoring the downloaded files rather than committing them (see Assumptions) |
| Cost/rate limits on cloud provider | Provider abstraction makes it a one-line config change to fall back to Ollama-only |

## 8. Implementation Plan (priority order)

**P0:** FastAPI + Postgres/pgvector + ingestion + retrieval + grounded answers + citations + persistence +
Ollama + cloud provider + provider switching + artifact generation + secure viewer + working frontend +
Docker startup.

**P1:** Streaming, UI states (loading/empty/error/streaming), source cards, responsive design, structured
logging, resilience, automated tests, complete docs.

**P2 (only if time remains):** Cosmetic polish, animations — deliberately minimized per the assignment's
own "avoid over-engineering" guidance.
