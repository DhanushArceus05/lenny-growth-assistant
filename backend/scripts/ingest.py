"""
Transcript ingestion pipeline: parse -> chunk -> embed -> store in Postgres/pgvector.

Requires a running Postgres with the pgvector extension available (the `db` service
in docker-compose.yml uses the `pgvector/pgvector:pg16` image, which has it
preinstalled). Creates the `transcript_chunks` table + HNSW index on first run.

Parses front-matter from either real Lenny's Podcast transcript exports (title,
guest, date, and — on many episodes — video_id/youtube_url/post_url for a real
traceable citation link) or the hand-authored synthetic fixtures in
sample_transcripts/ (title/guest/date only, file path used as the citation).

Usage (from backend/, with DATABASE_URL pointed at a real Postgres):
    # Real data — after running `python -m scripts.download_transcripts` (see its docstring)
    python -m scripts.ingest --source-dir data/lennys_podcast

    # Synthetic demo/test fixtures (no network required)
    python -m scripts.ingest --source-dir sample_transcripts
"""
import argparse
import asyncio
import sys
from datetime import date as date_type
from pathlib import Path

import frontmatter
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.logging_config import configure_logging, get_logger  # noqa: E402
from app.rag.chunking import chunk_transcript, timestamp_to_seconds  # noqa: E402
from app.rag.embeddings import EmbeddingService  # noqa: E402

logger = get_logger("ingest")

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS transcript_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_title   TEXT NOT NULL,
    guest_name      TEXT,
    published_at    DATE,
    timestamp_ref   TEXT,
    source_location TEXT,
    chunk_index     INT NOT NULL,
    chunk_text      TEXT NOT NULL,
    embedding       VECTOR({dim}),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS transcript_chunks_embedding_hnsw
    ON transcript_chunks USING hnsw (embedding vector_cosine_ops);
"""

INSERT_SQL = text(
    """
    INSERT INTO transcript_chunks
        (episode_title, guest_name, published_at, timestamp_ref, source_location, chunk_index, chunk_text, embedding)
    VALUES
        (:episode_title, :guest_name, :published_at, :timestamp_ref, :source_location, :chunk_index, :chunk_text, CAST(:embedding AS vector))
    """
)


async def ensure_schema(dim: int) -> None:
    async with engine.begin() as conn:
        for statement in CREATE_TABLE_SQL.format(dim=dim).split(";"):
            if statement.strip():
                await conn.execute(text(statement))


async def ingest_file(path: Path, embedding_service: EmbeddingService, settings) -> int:
    post = frontmatter.load(path)
    episode_title = post.get("title", path.stem)
    guest_name = post.get("guest")
    published_at = _parse_date(post.get("date"))
    video_id = post.get("video_id")
    youtube_url = post.get("youtube_url")
    post_url = post.get("post_url")

    chunks = chunk_transcript(post.content, settings.CHUNK_TARGET_TOKENS, settings.CHUNK_OVERLAP_TOKENS)
    if not chunks:
        logger.warning("ingest.no_chunks", file=str(path))
        return 0

    embeddings = await embedding_service.embed_batch([c.text for c in chunks])

    async with engine.begin() as conn:
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            source_location = _build_source_location(
                video_id=video_id,
                youtube_url=youtube_url,
                post_url=post_url,
                path=path,
                timestamp_ref=chunk.timestamp_ref,
            )
            await conn.execute(
                INSERT_SQL,
                {
                    "episode_title": episode_title,
                    "guest_name": guest_name,
                    "published_at": published_at,
                    "timestamp_ref": chunk.timestamp_ref,
                    "source_location": source_location,
                    "chunk_index": chunk.chunk_index,
                    "chunk_text": chunk.text,
                    "embedding": str(embedding),
                },
            )
    logger.info("ingest.file_complete", file=str(path), chunks=len(chunks))
    return len(chunks)


def _parse_date(raw_date) -> "date_type | None":
    """Front-matter `date` values come from real transcript exports as quoted
    strings (e.g. "2026-08-16") or, for hand-authored fixtures, sometimes as YAML
    dates already. Normalizes both to a plain ISO date, or None if unparseable —
    a bad date shouldn't fail the whole ingest run."""
    if raw_date is None:
        return None
    if isinstance(raw_date, date_type):
        return raw_date
    try:
        return date_type.fromisoformat(str(raw_date)[:10])
    except ValueError:
        return None


def _build_source_location(video_id, youtube_url, post_url, path: Path, timestamp_ref: str | None) -> str:
    """Prefers the most specific traceable link available in the real dataset's
    front-matter: a YouTube deep link to the exact moment (when both a video ID and
    a parseable chunk timestamp exist), then a plain YouTube URL, then the
    newsletter post URL, then finally the local file path (synthetic/local-only
    fixtures)."""
    if video_id:
        seconds = timestamp_to_seconds(timestamp_ref) if timestamp_ref else None
        if seconds is not None:
            return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"
    if youtube_url:
        return youtube_url
    if post_url:
        return post_url
    return str(path)


async def main_async(source_dir: Path) -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    await ensure_schema(settings.EMBEDDING_DIMENSION)

    embedding_service = EmbeddingService(settings)
    files = sorted(source_dir.glob("*.md"))
    if not files:
        logger.error("ingest.no_files_found", source_dir=str(source_dir))
        print(f"No .md files found in {source_dir}")
        return

    total = 0
    for f in files:
        try:
            total += await ingest_file(f, embedding_service, settings)
        except Exception as exc:  # noqa: BLE001
            logger.error("ingest.file_failed", file=str(f), error=str(exc))
            print(f"FAILED: {f.name}: {exc}")

    print(f"Ingested {total} chunks from {len(files)} file(s) into transcript_chunks.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", default="sample_transcripts")
    args = parser.parse_args()
    asyncio.run(main_async(Path(args.source_dir)))


if __name__ == "__main__":
    main()
