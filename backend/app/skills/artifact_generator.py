"""
Extracts <artifact type="markdown|html" title="...">...</artifact> blocks from a
completed model response into structured Artifact records, and returns the
chat-visible text with those blocks replaced by a short reference chip — so the
chat pane shows a pointer to the artifact pane instead of a wall of raw markup.
"""
import re
from dataclasses import dataclass

_ARTIFACT_RE = re.compile(
    r'<artifact\s+type="(?P<type>markdown|html)"\s+title="(?P<title>[^"]*)"\s*>(?P<body>.*?)</artifact>',
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class ExtractedArtifact:
    artifact_type: str
    title: str
    content: str


def extract_artifacts(raw_response: str) -> tuple[str, list[ExtractedArtifact]]:
    artifacts: list[ExtractedArtifact] = []

    def _replace(match: re.Match) -> str:
        artifacts.append(
            ExtractedArtifact(
                artifact_type=match.group("type").lower(),
                title=match.group("title") or "Untitled artifact",
                content=match.group("body").strip(),
            )
        )
        return f'\n📄 *Opened "{match.group("title") or "artifact"}" in the artifact pane.*\n'

    visible_text = _ARTIFACT_RE.sub(_replace, raw_response)
    return visible_text.strip(), artifacts


def wrap_as_markdown_artifact(title: str, content: str) -> ExtractedArtifact:
    """Ship30 essays and explicit 'generate a doc' requests don't require the model
    to remember the <artifact> tag syntax — the caller can wrap the whole response."""
    return ExtractedArtifact(artifact_type="markdown", title=title, content=content.strip())
