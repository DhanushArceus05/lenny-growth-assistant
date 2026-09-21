"""
Recursive character-based chunking with token-aware sizing and overlap, plus
timestamp-marker tracking so each chunk can point back to roughly where in the
episode it came from.

Kept dependency-light: token counts are approximated (~4 chars/token, the standard
rule-of-thumb for English text) rather than pulling in a real tokenizer. This is a
deliberate trade-off — tiktoken's BPE file is fetched from a remote blob store at
import time, which is an unnecessary runtime dependency for what only needs to be a
"roughly 500-800 tokens" chunk-size heuristic, not exact token accounting (the LLM
provider APIs do their own real tokenization on the actual request).
"""
import re
from dataclasses import dataclass

_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]|\((\d{1,2}:\d{2}(?::\d{2})?)\)")

_SEPARATORS = ["\n\n", "\n", ". ", " "]

_CHARS_PER_TOKEN = 4


def _token_len(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _split_on(text: str, sep: str) -> list[str]:
    parts = text.split(sep)
    return [p + sep for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def _recursive_split(text: str, max_tokens: int, separators: list[str]) -> list[str]:
    if _token_len(text) <= max_tokens or not separators:
        return [text]
    sep, rest = separators[0], separators[1:]
    pieces = _split_on(text, sep) if sep in text else [text]
    if len(pieces) == 1:
        return _recursive_split(text, max_tokens, rest)

    out: list[str] = []
    for piece in pieces:
        if _token_len(piece) > max_tokens:
            out.extend(_recursive_split(piece, max_tokens, rest))
        else:
            out.append(piece)
    return out


def _merge_with_overlap(pieces: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    """Greedily pack small pieces together up to max_tokens, carrying `overlap_tokens`
    worth of trailing text forward into the next chunk for continuity."""
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = current + piece
        if _token_len(candidate) <= max_tokens or not current:
            current = candidate
        else:
            chunks.append(current.strip())
            overlap_text = _tail_by_tokens(current, overlap_tokens)
            current = overlap_text + piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _tail_by_tokens(text: str, n_tokens: int) -> str:
    n_chars = n_tokens * _CHARS_PER_TOKEN
    return text[-n_chars:] if len(text) > n_chars else text


def _nearest_timestamp(text: str) -> str | None:
    matches = _TIMESTAMP_RE.findall(text)
    if not matches:
        return None
    first = matches[0]
    return first[0] or first[1]


def timestamp_to_seconds(ts: str) -> int | None:
    """Converts 'HH:MM:SS' or 'MM:SS' to total seconds, for building a deep link
    into the source video/audio at the right moment. Returns None for anything
    that isn't a clean timestamp (e.g. a topic label used in place of a real
    timestamp for hand-authored transcripts)."""
    if not ts:
        return None
    parts = ts.split(":")
    if not all(p.isdigit() for p in parts) or len(parts) not in (2, 3):
        return None
    parts = [int(p) for p in parts]
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0
    else:
        hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


@dataclass
class Chunk:
    text: str
    chunk_index: int
    timestamp_ref: str | None


def chunk_transcript(body: str, target_tokens: int = 650, overlap_tokens: int = 100) -> list[Chunk]:
    raw_pieces = _recursive_split(body, target_tokens, _SEPARATORS)
    merged = _merge_with_overlap(raw_pieces, target_tokens, overlap_tokens)
    return [
        Chunk(text=text, chunk_index=i, timestamp_ref=_nearest_timestamp(text))
        for i, text in enumerate(merged)
        if text.strip()
    ]
