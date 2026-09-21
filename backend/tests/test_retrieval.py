"""
The highest-risk path in the whole assignment: does the assistant correctly refuse
to answer when retrieval is weak, instead of hallucinating? Tested at the unit level
against a mocked AsyncSession (transcript_chunks is pgvector-only, not sqlite-portable
— see conftest.py docstring), plus the grounded-prompt builder that consumes it.
"""
from unittest.mock import AsyncMock, MagicMock

from app.rag.retriever import RetrievedChunk, TranscriptRetriever
from app.skills.grounded_chat import build_grounded_prompt


def _fake_row(score, episode="Ep", guest="Guest", ts="00:01:00", loc="f.md", txt="text"):
    row = MagicMock()
    row.episode_title = episode
    row.guest_name = guest
    row.chunk_text = txt
    row.timestamp_ref = ts
    row.source_location = loc
    row.similarity_score = score
    return row


async def test_retrieve_fetches_a_wider_candidate_pool_than_top_k():
    """The core fix: SQL LIMIT should use the (larger) candidate pool, not
    top_k — the prior implementation fetched only top_k=5 candidates, so a
    relevant chunk ranked 6th-15th by raw vector distance could never be
    surfaced no matter how the threshold/margin were tuned. This is exactly
    what the live diagnostic against the real corpus found (Mark Pincus'
    growth-loops chunk wasn't in the old top-5 fetch window at all)."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.9)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    await retriever.retrieve("some query", top_k=5, candidate_pool=15)

    _, bound_params = db.execute.call_args.args
    assert bound_params["limit"] == 15, "SQL LIMIT should use candidate_pool, not top_k"


async def test_retrieve_candidate_pool_defaults_wider_than_top_k_when_unset():
    """Callers that don't explicitly pass candidate_pool (as existing tests and
    call sites predate this change) should still get a wider-than-top_k fetch
    automatically, not silently fall back to the old top_k-only behavior."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.9)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    await retriever.retrieve("some query", top_k=5)

    _, bound_params = db.execute.call_args.args
    assert bound_params["limit"] > 5
    assert bound_params["limit"] == 15


async def test_retrieve_caps_final_results_at_top_k_even_with_more_candidates():
    """Widening the candidate pool must not widen the final result count — the
    LLM should still see at most top_k chunks. Simulates 15 fetched candidates
    where 8 pass both filter stages; only the best 5 (top_k) should return."""
    db = AsyncMock()
    result = MagicMock()
    # 8 chunks clustered close enough together to all survive stage 1 + stage 2.
    result.fetchall.return_value = [_fake_row(0.90 - i * 0.01) for i in range(8)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    chunks = await retriever.retrieve(
        "some query", top_k=5, similarity_threshold=0.35, relative_margin=0.15, candidate_pool=15
    )

    assert len(chunks) == 5
    # Still the 5 highest-scoring of the 8 candidates, in descending order.
    assert [round(c.score, 2) for c in chunks] == [0.90, 0.89, 0.88, 0.87, 0.86]


async def test_retrieve_explicit_candidate_pool_overrides_default():
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.9)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    await retriever.retrieve("some query", top_k=5, candidate_pool=25)

    _, bound_params = db.execute.call_args.args
    assert bound_params["limit"] == 25


async def test_retrieve_filters_below_absolute_threshold():
    """Stage 1 (absolute floor) in isolation — relative_margin set wide open so
    stage 2 doesn't interfere with this assertion."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.8), _fake_row(0.5), _fake_row(0.1)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    chunks = await retriever.retrieve("some query", top_k=5, similarity_threshold=0.35, relative_margin=1.0)

    assert len(chunks) == 2
    assert all(c.score >= 0.35 for c in chunks)


async def test_retrieve_drops_weak_chunks_relative_to_a_strong_top_match():
    """Stage 2 (relative dominance) — a standout top match (0.8) should drop a
    chunk (0.5) that individually clears the absolute floor but trails the best
    match by more than the configured margin. This is the fix for the reported
    symptom: a confidently-answerable question shouldn't get diluted by a
    barely-related chunk riding along just because it cleared 0.35."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.8), _fake_row(0.5)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    chunks = await retriever.retrieve("some query", top_k=5, similarity_threshold=0.35, relative_margin=0.15)

    assert len(chunks) == 1
    assert chunks[0].score == 0.8


async def test_retrieve_keeps_tightly_clustered_chunks_together():
    """When there's no standout top match — scores close together — the
    relative-margin filter should be a no-op; several genuinely-comparable
    chunks are legitimate multi-source evidence, not dilution."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.62), _fake_row(0.58), _fake_row(0.51)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    chunks = await retriever.retrieve("some query", top_k=5, similarity_threshold=0.35, relative_margin=0.15)

    assert len(chunks) == 3


async def test_retrieve_returns_empty_when_nothing_matches():
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = [_fake_row(0.1), _fake_row(0.05)]
    db.execute.return_value = result

    embedding_service = AsyncMock()
    embedding_service.embed.return_value = [0.0] * 384

    retriever = TranscriptRetriever(db, embedding_service)
    chunks = await retriever.retrieve("out of domain query", similarity_threshold=0.35)

    assert chunks == []
    assert TranscriptRetriever.is_sufficiently_grounded(chunks) is False


def test_grounded_prompt_triggers_refusal_instruction_when_no_chunks():
    prompt = build_grounded_prompt([])
    assert prompt.grounded is False
    assert "don't have enough information" in prompt.system_prompt


def test_grounded_prompt_includes_citations_when_chunks_present():
    chunks = [
        RetrievedChunk(episode="Onboarding Ep", guest="Priya Shah", text="some insight", timestamp="00:02:10",
                        source_location="f.md", score=0.8)
    ]
    prompt = build_grounded_prompt(chunks)
    assert prompt.grounded is True
    assert "Priya Shah" in prompt.system_prompt
    assert "Onboarding Ep" in prompt.system_prompt


def test_grounded_prompt_labels_each_excerpt_with_its_relevance_score():
    """The model gets an explicit confidence signal per excerpt rather than
    having to infer relevance from the text alone — added specifically so a
    small local model doesn't treat a borderline excerpt as equally strong
    evidence as a clearly on-topic one."""
    chunks = [
        RetrievedChunk(episode="Onboarding Ep", guest="Priya Shah", text="some insight", timestamp="00:02:10",
                        source_location="f.md", score=0.81),
        RetrievedChunk(episode="Pricing Ep", guest="Marcus Lee", text="other insight", timestamp="00:05:00",
                        source_location="f2.md", score=0.47),
    ]
    prompt = build_grounded_prompt(chunks)
    assert "relevance: 0.81" in prompt.system_prompt
    assert "relevance: 0.47" in prompt.system_prompt
    assert "weigh higher-relevance excerpts" in prompt.system_prompt.lower()
