"""FastAPI application entrypoint. CORS, structured logging, and global exception
handlers are wired here; route logic lives in app/api/*."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api import chat, health, providers, sessions
from app.config import get_settings
from app.database import init_models
from app.logging_config import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates the sessions/messages/artifacts tables on first run (idempotent —
    # SQLAlchemy's create_all only issues CREATE TABLE for tables that don't
    # already exist, so this is a no-op on every startup after the first, and
    # never touches transcript_chunks — that table lives outside Base.metadata
    # and is only ever created/written by scripts/ingest.py, see database.py).
    #
    # A DB that's briefly unreachable at startup shouldn't take the whole app
    # down: log it and let uvicorn come up anyway, so /api/health can still
    # report `database: false` instead of the container failing to start at all.
    try:
        await init_models()
        logger.info("startup.db_initialized")
    except Exception as exc:  # noqa: BLE001 - startup must not crash the whole app
        logger.error("startup.db_initialization_failed", error=str(exc))
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(providers.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("request.validation_error", path=str(request.url), errors=exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request failed validation.",
                "detail": str(exc.errors()),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("request.unhandled_exception", path=str(request.url), error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
    )


@app.get("/")
async def root():
    return {"service": settings.APP_NAME, "status": "running"}
