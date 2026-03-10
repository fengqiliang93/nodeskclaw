"""SSEConnection — tracks active SSE connections across backend instances."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SSEConnection(BaseModel):
    __tablename__ = "sse_connections"

    connection_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    backend_instance_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
