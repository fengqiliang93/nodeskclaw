"""IdempotencyCache — deduplication cache for at-least-once message delivery."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IdempotencyCache(BaseModel):
    __tablename__ = "idempotency_cache"

    message_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
