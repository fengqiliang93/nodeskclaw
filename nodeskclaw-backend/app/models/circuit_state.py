"""CircuitState — per-node circuit breaker state persistence."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class CircuitState(BaseModel):
    __tablename__ = "circuit_states"
    __table_args__ = (
        Index(
            "uq_circuit_state_node_workspace",
            "node_id",
            "workspace_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    node_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(16), default="closed", nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    half_open_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
