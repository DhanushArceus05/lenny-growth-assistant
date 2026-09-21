from app.rag.retriever import RetrievedChunk
from app.skills.ship30_writer import build_ship30_prompt


def test_ship30_prompt_targets_word_count_and_includes_context():
    chunks = [
        RetrievedChunk(episode="Pricing Ep", guest="Marcus Lee", text="usage-based pricing insight",
                        timestamp="00:09:40", source_location="f.md", score=0.7)
    ]
    prompt = build_ship30_prompt("how should I think about pricing?", chunks)
    assert "1250" in prompt.system_prompt or "1,250" in prompt.system_prompt
    assert "Marcus Lee" in prompt.user_prompt
    assert "Pricing Ep" in prompt.user_prompt
    assert "usage-based pricing insight" in prompt.user_prompt


def test_ship30_prompt_handles_no_context_gracefully():
    prompt = build_ship30_prompt("a totally out of scope question", [])
    assert "no supporting transcript context" in prompt.user_prompt
