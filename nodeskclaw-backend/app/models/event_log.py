"""EventLog — append-only event sourcing log for message lifecycle tracking."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EventLog(BaseModel):
    __tablename__ = "event_logs"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
