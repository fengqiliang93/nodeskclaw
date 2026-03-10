"""DeadLetter — messages that exceeded retry limits, awaiting manual intervention."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class DeadLetter(BaseModel):
    __tablename__ = "dead_letters"

    message_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_node_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    original_priority: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    envelope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
