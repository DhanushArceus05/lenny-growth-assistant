from app.rag.chunking import chunk_transcript


SAMPLE = """[00:01:00] Speaker: """ + ("This is a sentence about growth loops and onboarding. " * 60) + \
    """\n\n[00:05:30] Speaker: """ + ("A second section discussing pricing experiments in depth. " * 60)


def test_chunking_respects_target_token_budget_roughly():
    chunks = chunk_transcript(SAMPLE, target_tokens=200, overlap_tokens=30)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text) > 0


def test_chunking_captures_timestamps():
    chunks = chunk_transcript(SAMPLE, target_tokens=200, overlap_tokens=30)
    timestamps = [c.timestamp_ref for c in chunks if c.timestamp_ref]
    assert "00:01:00" in timestamps or "00:05:30" in timestamps


def test_chunking_overlap_produces_shared_text_between_consecutive_chunks():
    chunks = chunk_transcript(SAMPLE, target_tokens=150, overlap_tokens=40)
    assert len(chunks) >= 2
    # crude overlap check: some trailing words of chunk[0] should reappear at the
    # start of chunk[1] because of the token-tail carry-forward
    tail_words = chunks[0].text.split()[-5:]
    assert any(w in chunks[1].text for w in tail_words)


def test_empty_input_produces_no_chunks():
    assert chunk_transcript("", target_tokens=200, overlap_tokens=30) == []
