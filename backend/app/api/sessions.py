from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import Message as MessageModel
from app.models.db_models import Session as SessionModel
from app.models.schemas import SessionCreate, SessionDetail, SessionOut

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)) -> SessionOut:
    session = SessionModel(title=body.title or "New conversation")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.get("", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionOut]:
    result = await db.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()))
    return [SessionOut.model_validate(s) for s in result.scalars().all()]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> SessionDetail:
    # Async ORM relationships need an explicit eager-load strategy or a MissingGreenlet
    # error occurs when Pydantic touches `.messages` outside the session context.
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.id == session_id)
        .options(selectinload(SessionModel.messages).selectinload(MessageModel.artifacts))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "session not found"}})
    return SessionDetail.model_validate(session)
