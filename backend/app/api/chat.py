"""
POST /api/chat — the only place that wires retrieval + skills + provider +
persistence together. No provider-specific branching lives here (see
providers/factory.py), and no prompt text lives here (see app/skills/*).
"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.logging_config import get_logger
from app.models.db_models import Artifact as ArtifactModel
from app.models.db_models import Message as MessageModel
from app.models.db_models import Session as SessionModel
from app.models.schemas import ChatRequest
from app.providers.base import ChatMessage, ProviderTimeoutError, ProviderUnavailableError
from app.providers.factory import get_provider
from app.rag.embeddings import EmbeddingService
from app.rag.retriever import TranscriptRetriever
from app.skills.artifact_generator import extract_artifacts, wrap_as_markdown_artifact
from app.skills.grounded_chat import build_grounded_prompt
from app.skills.ship30_writer import build_ship30_prompt

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = get_logger(__name__)


def _sse(event_type: str, payload: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


async def _load_history(db: AsyncSession, session_id: str, limit: int = 20) -> list[ChatMessage]:
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.session_id == session_id, MessageModel.role.in_(["user", "assistant"]))
        .order_by(MessageModel.created_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [ChatMessage(role=m.role, content=m.content) for m in rows]


def _previous_user_message(history: list[ChatMessage], current_message: str) -> str | None:
    """The turn before the current one, used to expand a thin follow-up query for
    retrieval (e.g. "what about for freemium?" on its own retrieves poorly; combined
    with the prior turn it retrieves the right chunks). `history` includes the
    just-persisted current user message as its last entry, so we look one before that."""
    user_turns = [m.content for m in history if m.role == "user"]
    if user_turns and user_turns[-1] == current_message:
        user_turns = user_turns[:-1]
    return user_turns[-1] if user_turns else None


def _source_url_for(source_location: str | None) -> str | None:
    """Only surface a citation link when it's an actual URL (real transcript data
    with a YouTube/newsletter link) — a local file path (synthetic fixtures) isn't
    meaningful or safe to show a user."""
    if source_location and source_location.startswith("http"):
        return source_location
    return None


@router.post("")
async def stream_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    session_result = await db.execute(select(SessionModel).where(SessionModel.id == req.session_id))
    session = session_result.scalar_one_or_none()
    if session is None:
        return StreamingResponse(
            iter([_sse("error", {"code": "not_found", "message": "session not found"})]),
            media_type="text/event-stream",
        )

    user_message = MessageModel(session_id=session.id, role="user", content=req.message)
    db.add(user_message)
    await db.commit()

    async def event_generator():
        log = logger.bind(session_id=session.id, mode=req.mode, requested_provider=req.provider)
        try:
            yield _sse("status", {"content": "Searching the archive…"})

            embedding_service = EmbeddingService(settings)
            retriever = TranscriptRetriever(db, embedding_service)
            history = await _load_history(db, session.id)
            try:
                chunks = await retriever.retrieve(
                    req.message,
                    top_k=settings.RETRIEVAL_TOP_K,
                    similarity_threshold=settings.RETRIEVAL_SIMILARITY_THRESHOLD,
                    relative_margin=settings.RETRIEVAL_RELATIVE_MARGIN,
                    candidate_pool=settings.RETRIEVAL_CANDIDATE_POOL,
                )
                retrieval_expanded = False
                if not chunks:
                    # A thin follow-up ("what about for freemium?") often retrieves
                    # nothing on its own even though the conversation clearly has
                    # enough context. Retry once with the prior turn folded in
                    # before concluding the archive genuinely has no answer — this
                    # keeps the refusal path strict for truly out-of-domain
                    # questions while not penalizing legitimate follow-ups.
                    previous = _previous_user_message(history, req.message)
                    if previous:
                        chunks = await retriever.retrieve(
                            f"{previous} {req.message}",
                            top_k=settings.RETRIEVAL_TOP_K,
                            similarity_threshold=settings.RETRIEVAL_SIMILARITY_THRESHOLD,
                            relative_margin=settings.RETRIEVAL_RELATIVE_MARGIN,
                            candidate_pool=settings.RETRIEVAL_CANDIDATE_POOL,
                        )
                        retrieval_expanded = bool(chunks)
            except Exception as exc:
                log.error("chat.retrieval_failed", error=str(exc))
                yield _sse(
                    "error",
                    {
                        "code": "retrieval_failed",
                        "message": "Couldn't search the transcript archive (has it been ingested yet?).",
                    },
                )
                return
            if retrieval_expanded:
                log.info("chat.retrieval_expanded_for_followup")

            sources_payload = [
                {
                    "episode": c.episode,
                    "guest": c.guest,
                    "timestamp": c.timestamp,
                    "score": round(c.score, 3),
                    "excerpt": c.text[:280],
                    # Only surface source_location as a clickable citation when it's
                    # an actual URL (real transcript data) — a local file path
                    # (synthetic fixtures) isn't meaningful or safe to show a user.
                    "source_url": _source_url_for(c.source_location),
                }
                for c in chunks
            ]
            if sources_payload:
                yield _sse("sources", {"sources": sources_payload})

            if req.mode == "ship30":
                prompt = build_ship30_prompt(req.message, chunks, settings)
                grounded = len(chunks) > 0
            else:
                grounded_prompt = build_grounded_prompt(chunks)
                prompt = grounded_prompt
                grounded = grounded_prompt.grounded

            try:
                provider = get_provider(req.provider)
            except ValueError as exc:
                yield _sse("error", {"code": "bad_provider", "message": str(exc)})
                return

            available, reason = await provider.check_available()
            if not available:
                log.warning("chat.provider_unavailable", provider=provider.name, reason=reason)
                yield _sse(
                    "error",
                    {
                        "code": "provider_unavailable",
                        "message": f"{provider.name} is unavailable: {reason}",
                    },
                )
                return

            system_prompt = prompt.system_prompt if req.mode == "ship30" else prompt.system_prompt
            messages_for_provider = history if req.mode != "ship30" else [
                ChatMessage(role="user", content=prompt.user_prompt)
            ]

            full_text = ""
            try:
                async for token in provider.generate_response(messages_for_provider, system_prompt):
                    full_text += token
                    yield _sse("token", {"content": token})
            except ProviderUnavailableError as exc:
                log.error("chat.provider_error", provider=exc.provider, reason=exc.reason)
                yield _sse("error", {"code": "provider_unavailable", "message": str(exc)})
                return
            except ProviderTimeoutError as exc:
                log.error("chat.provider_timeout", provider=exc.provider)
                yield _sse("error", {"code": "provider_timeout", "message": f"{exc.provider} timed out"})
                return

            if not full_text.strip():
                yield _sse("error", {"code": "empty_response", "message": "Model returned an empty response."})
                return

            visible_text, extracted = extract_artifacts(full_text)
            if req.mode == "ship30" and not extracted:
                # Ship30 always produces a document even if the model forgot the <artifact> tag.
                extracted = [wrap_as_markdown_artifact(f"Ship 30: {req.message[:60]}", full_text)]
                visible_text = f'📄 *Opened "Ship 30: {req.message[:60]}" in the artifact pane.*'

            assistant_message = MessageModel(
                session_id=session.id,
                role="assistant",
                content=visible_text,
                sources=sources_payload,
                provider=provider.name,
            )
            db.add(assistant_message)
            await db.flush()

            artifact_payloads = []
            for art in extracted:
                artifact_row = ArtifactModel(
                    message_id=assistant_message.id,
                    artifact_type=art.artifact_type,
                    title=art.title,
                    content=art.content,
                )
                db.add(artifact_row)
                artifact_payloads.append(
                    {"artifact_type": art.artifact_type, "title": art.title, "content": art.content}
                )

            if session.title == "New conversation":
                session.title = req.message[:60]
            await db.commit()

            for artifact in artifact_payloads:
                yield _sse("artifact", artifact)

            yield _sse("done", {"grounded": grounded, "message_id": assistant_message.id})
        except Exception as exc:  # noqa: BLE001 - last-resort guard so SSE always terminates cleanly
            log.error("chat.unhandled_error", error=str(exc), exc_info=True)
            yield _sse("error", {"code": "internal_error", "message": "Something went wrong processing your message."})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
