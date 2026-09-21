from app.skills.artifact_generator import extract_artifacts, wrap_as_markdown_artifact


def test_extract_single_html_artifact():
    raw = (
        'Here is your one-pager:\n'
        '<artifact type="html" title="Onboarding One-Pager"><html><body><h1>Hi</h1></body></html></artifact>\n'
        'Let me know if you want changes.'
    )
    visible, artifacts = extract_artifacts(raw)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "html"
    assert artifacts[0].title == "Onboarding One-Pager"
    assert "<h1>Hi</h1>" in artifacts[0].content
    assert "<artifact" not in visible
    assert "artifact pane" in visible


def test_extract_no_artifacts_returns_original_text():
    raw = "Just a normal grounded answer with no artifact."
    visible, artifacts = extract_artifacts(raw)
    assert artifacts == []
    assert visible == raw


def test_extract_markdown_artifact():
    raw = '<artifact type="markdown" title="Ship 30 Essay">\n# Hook\nBody text.\n</artifact>'
    visible, artifacts = extract_artifacts(raw)
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == "markdown"
    assert "# Hook" in artifacts[0].content


def test_wrap_as_markdown_artifact_strips_whitespace():
    artifact = wrap_as_markdown_artifact("Title", "  content with padding  \n")
    assert artifact.content == "content with padding"
    assert artifact.artifact_type == "markdown"
