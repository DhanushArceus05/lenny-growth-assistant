from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.models.schemas import HealthStatus
from app.providers.factory import list_provider_status

router = APIRouter(prefix="/api", tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthStatus)
async def health(db: AsyncSession = Depends(get_db)) -> HealthStatus:
    db_ok = False
    vector_populated = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
        try:
            result = await db.execute(text("SELECT COUNT(*) FROM transcript_chunks"))
            vector_populated = (result.scalar() or 0) > 0
        except Exception:
            vector_populated = False  # table may not exist yet (pre-ingestion) — not a DB failure
    except Exception as exc:
        logger.error("health.database_check_failed", error=str(exc))

    providers = await list_provider_status()
    ollama_reachable = any(p.name == "ollama" and p.available for p in providers)

    status = "ok" if db_ok and (ollama_reachable or any(p.available for p in providers)) else "degraded"
    return HealthStatus(
        status=status,
        database=db_ok,
        ollama_reachable=ollama_reachable,
        vector_index_populated=vector_populated,
        providers=providers,
    )
