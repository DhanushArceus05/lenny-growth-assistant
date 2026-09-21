# Session 8 — Candidate-pool widening, driven by a live diagnostic

**Context:** A live RAG diagnostic against the real 675-chunk Postgres corpus
found a concrete failure case: a growth-loops question's best retrieval score
was only 0.37 (Ian Silber), and the actually-relevant chunk — a real Mark
Pincus episode at 00:46:44 discussing feedback loops and an engagement metric
(ASN) — wasn't in the top 15 nearest neighbors for that query at all. The
instruction was explicit and evidence-based: don't lower the threshold further
(that would only make refusal stricter without fixing why the right chunk
wasn't found), and don't hardcode a "growth loop" keyword — fix the retrieval
architecture generically instead.

## Why this contradicted my own prior session's default

Session 7 had raised `RETRIEVAL_SIMILARITY_THRESHOLD`'s default from 0.35 to
0.45, reasoning from documented MiniLM behavior but explicitly flagged as *not*
numerically validated against the real corpus (no Postgres available in this
sandbox). This session's live diagnostic is exactly that missing validation —
and it points the other way: the corpus's best legitimate match for a real
question scored 0.37, which a 0.45 floor would have refused outright even
though relevant content existed. **Reverted the default back to 0.35**, per
explicit instruction and the actual evidence, and documented why directly in
`config.py`'s comment rather than leaving two sessions' reasoning silently in
tension with each other.

## The actual fix: widen retrieval recall, not filtering precision

The root problem Sessions 6/7 didn't address: `TranscriptRetriever.retrieve()`
only ever fetched `top_k` (5) candidates from SQL in the first place
(`LIMIT :top_k`). No amount of threshold or relative-margin tuning downstream
can ever surface a relevant chunk that was never fetched at all. This is a
recall problem at the SQL layer, not a precision problem in the filtering
logic that was already added.

**Fix:** `retrieve()` now takes a separate `candidate_pool` parameter (default
`max(top_k * 3, 15)`, and explicitly `RETRIEVAL_CANDIDATE_POOL=15` from both
`api/chat.py` call sites) that controls the SQL `LIMIT`, while `top_k` is now
purely a post-filter cap (`chunks[:top_k]` as the last step). Threshold (0.35)
and relative-margin (0.15) logic are completely unchanged — same two stages,
same order, just operating over more candidates than before.

## What this does and doesn't fix

Generic, not growth-loops-specific: any query where the right chunk ranks
6th-15th by raw embedding distance (rather than 1st-5th) now has a chance to be
found and pass the existing filters, for any topic — nothing query-specific was
added anywhere in this change.

**Honest limitation, stated plainly rather than overclaimed:** the diagnostic
that motivated this said the Mark Pincus chunk wasn't in the top *15* either —
so this specific example may still fail even with the fix, if its true rank is
beyond 15. That's a chunking/embedding-granularity question (is the "feedback
loops" content split across a chunk boundary such that no single chunk's
embedding centers on it?), which is out of scope for this pass — this was
authorized as a retrieval-architecture fix, not a chunking-strategy change,
and I didn't touch chunking. `RETRIEVAL_CANDIDATE_POOL` is tunable higher if
future diagnostics show the right rank is regularly beyond 15.

## Tests

`tests/test_retrieval.py`: 4 new tests — SQL `LIMIT` uses `candidate_pool` not
`top_k`; the default widens automatically even for callers that don't pass it
explicitly (existing call sites/tests predate this parameter); final result is
still capped at `top_k` even when more candidates pass both filter stages;
explicit `candidate_pool` overrides the default. Verified 3 of the 4 are real
regression tests (fail against the reverted old `LIMIT :top_k` behavior, pass
against the fix) — same discipline as the datetime-bug and prior RAG sessions.
The 4th (final-result capping) holds under both old and new code by
construction and is documented as such rather than miscounted as a regression
guard.

## Verified this session
- 61/61 backend tests pass (57 baseline + 4 new).
- Confirmed regression coverage empirically (reverted, watched 3/4 new tests
  fail as predicted, restored, re-verified all pass).
- `.env.example`, `README.md`, `docs/architecture.md` reconciled — no stale
  0.45 references left, three-stage flow (widen → absolute floor → relative
  dominance → cap) documented accurately.
- No frontend files touched; UI/Docker/Ollama model/provider config/ingestion
  untouched, per explicit scope.

## Not verified — requires your live stack
Whether this actually surfaces better chunks for real queries against your
675-chunk corpus, and specifically whether the Mark Pincus example now
resolves or needs `RETRIEVAL_CANDIDATE_POOL` raised further/a chunking
revisit — genuinely requires rerunning your diagnostic against the deployed
fix.
