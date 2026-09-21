"""
Turns a user query into ranked, cited transcript chunks. Deliberately has zero
knowledge of LLM providers or prompt construction — see architecture.md §5 for why.
"""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings import EmbeddingService


@dataclass
class RetrievedChunk:
    episode: str
    guest: str | None
    text: str
    timestamp: str | None
    source_location: str | None
    score: float


class TranscriptRetriever:
    def __init__(self, db: AsyncSession, embedding_service: EmbeddingService):
        self.db = db
        self.embedding_service = embedding_service

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.35,
        relative_margin: float = 0.15,
        candidate_pool: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Two-stage relevance filter over a widened candidate pool.

        `candidate_pool` (defaults to `max(top_k * 3, 15)` when not given) is
        how many nearest neighbors pgvector fetches before filtering — distinct
        from `top_k`, which caps how many chunks are returned after filtering.
        This distinction matters: fetching only `top_k` candidates from SQL
        means a relevant chunk ranked 6th-15th by raw vector distance could
        never be surfaced no matter how the threshold/margin are tuned, since
        it was never even considered. Widening the SQL fetch first gives the
        filtering stages below a real chance to find it, without changing what
        "relevant enough" means.
        """
        pool_size = candidate_pool if candidate_pool is not None else max(top_k * 3, 15)
        query_vector = await self.embedding_service.embed(query)

        result = await self.db.execute(
            text(
                """
                SELECT
                    episode_title,
                    guest_name,
                    chunk_text,
                    timestamp_ref,
                    source_location,
                    1 - (embedding <=> CAST(:vector AS vector)) AS similarity_score
                FROM transcript_chunks
                ORDER BY embedding <=> CAST(:vector AS vector)
                LIMIT :limit
                """
            ),
            {"vector": str(query_vector), "limit": pool_size},
        )
        rows = result.fetchall()

        chunks = [
            RetrievedChunk(
                episode=r.episode_title,
                guest=r.guest_name,
                text=r.chunk_text,
                timestamp=r.timestamp_ref,
                source_location=r.source_location,
                score=float(r.similarity_score),
            )
            for r in rows
        ]
        # Stage 1 — absolute floor: applied here (not in SQL) so callers can
        # distinguish "nothing in the archive at all" from "matched, but too
        # weakly to trust" — both surface the same refusal, but this keeps the
        # reason inspectable/loggable.
        chunks = [c for c in chunks if c.score >= similarity_threshold]
        if not chunks:
            return chunks

        # Stage 2 — relative dominance: once there's a genuinely strong match,
        # don't dilute it with chunks that only individually cleared the floor.
        # rows are already ordered by score descending (nearest distance first).
        top_score = chunks[0].score
        chunks = [c for c in chunks if (top_score - c.score) <= relative_margin]

        # Cap the final result at top_k — the wider candidate_pool only exists
        # to give stages 1/2 more to choose from, not to change how many
        # chunks the LLM ultimately sees.
        return chunks[:top_k]

    @staticmethod
    def is_sufficiently_grounded(chunks: list[RetrievedChunk]) -> bool:
        return len(chunks) > 0
