# Session 7 — RAG grounding/source-quality pass

**Context:** Explicit focused-quality-pass request, RAG only, no UI, no
architecture changes: retrieval was occasionally surfacing weakly-relevant
chunks as if they were solid evidence, and a small local model
(`llama3.2:1b`) was prone to answering confidently from them anyway.

## Diagnosis (done before any edits, as instructed)

Inspected `rag/retriever.py`, `config.py`, `skills/grounded_chat.py`,
`api/chat.py`'s retrieval wiring, and `tests/test_retrieval.py`. Found three
compounding causes, not one:
1. `RETRIEVAL_SIMILARITY_THRESHOLD=0.35` is too permissive for MiniLM cosine
   similarity — topically-adjacent-but-unrelated excerpts often clear it.
2. No relative/dominance filtering — every chunk individually clearing the flat
   floor got kept and sent to the model with equal weight, even alongside a
   clearly-stronger match.
3. The prompt gave the model no per-excerpt confidence signal — every excerpt
   looked identical regardless of how strong its match actually was, which a
   1B model is especially bad at inferring from raw text alone.

## Fix (three small, additive changes — no schema change, no new dependency)

- `config.py`: raised `RETRIEVAL_SIMILARITY_THRESHOLD` default 0.35 → 0.45;
  added `RETRIEVAL_RELATIVE_MARGIN: float = 0.15`.
- `rag/retriever.py`: added a second filtering stage in `retrieve()` — after
  the absolute floor, drop any chunk scoring more than `relative_margin` below
  the single best match. Both stages independently loggable/inspectable.
- `skills/grounded_chat.py`: `_format_context` now labels each excerpt with
  `relevance: X.XX`; added one system-prompt rule telling the model to weigh
  by relevance and to refuse rather than stretch a moderate-relevance excerpt
  into an answer.
- `api/chat.py`: both `retrieve()` call sites (initial + follow-up-expanded
  retry) pass the new `relative_margin` setting through.
- Untouched, as scoped: chunking, DB schema, Ship 30 skill (benefits
  automatically since it consumes the same `retrieve()` output), session/
  follow-up logic, Ollama provider code, frontend/UI.

## Honesty note on the threshold values

I don't have Postgres or `sentence-transformers` in this sandbox, so 0.45 and
0.15 are *reasoned* defaults (documented in `config.py`, `.env.example`,
`architecture.md`, and README's Known Limitations) based on well-documented
MiniLM cosine-similarity behavior, not values I numerically tuned against your
real ingested corpus. Said this plainly rather than implying they were
empirically validated here.

## Test changes

`tests/test_retrieval.py`: the previous single threshold test
(`test_retrieve_filters_below_threshold`) was split — one version isolates
stage 1 by passing a wide-open `relative_margin=1.0` (preserves the original
test's intent), plus two new dedicated stage-2 tests: a standout top match
correctly drops a weaker also-ran, and a tightly-clustered set of scores is
correctly left untouched. Added one test asserting the prompt actually labels
each excerpt with its relevance score and includes the weighting instruction.

## Verified this session
- 57/57 backend tests pass (54 baseline + net +3 for the new/updated RAG
  coverage).
- Confirmed the new stage-2 filtering is genuinely active (not a no-op) by
  running the *old* test first and watching it fail exactly as predicted
  (2 chunks expected, 1 returned) before updating it — same discipline as the
  datetime-bug session's regression test.
- Full backend suite reran clean after all doc updates.

## Not verified — genuinely requires your local stack
- Whether 0.45/0.15 are actually the right values against your real 675-chunk
  corpus and `llama3.2:1b` specifically — needs your empirical testing.
- Whether the model actually follows the new relevance-weighting instruction
  in practice with a 1B model (system-prompt instructions are a strong nudge,
  not a hard guarantee, especially at this model size).
