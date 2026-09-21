"""Pydantic v2 request/response contracts. Kept separate from ORM models so the wire
format can evolve independently of storage."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceCitation(BaseModel):
    episode: str
    guest: str | None = None
    timestamp: str | None = None
    score: float
    excerpt: str
    source_url: str | None = None


class ArtifactOut(BaseModel):
    id: str
    artifact_type: Literal["markdown", "html"]
    title: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    sources: list[SourceCitation] = Field(default_factory=list)
    provider: str | None = None
    created_at: datetime
    artifacts: list[ArtifactOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    messages: list[MessageOut] = Field(default_factory=list)


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal["default", "ship30"] = "default"
    provider: Literal["ollama", "anthropic"] | None = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v


class ProviderStatus(BaseModel):
    name: str
    available: bool
    reason: str | None = None


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    ollama_reachable: bool
    vector_index_populated: bool
    providers: list[ProviderStatus]
