"""NodeCard — unified node representation for the workspace topology."""

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NodeCard(BaseModel):
    __tablename__ = "node_cards"
    __table_args__ = (
        Index(
            "uq_node_card_node_workspace",
            "node_id",
            "workspace_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_node_card_hex_pos",
            "workspace_id",
            "hex_q",
            "hex_r",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    node_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    hex_q: Mapped[int] = mapped_column(Integer, nullable=False)
    hex_r: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    workspace = relationship("Workspace", foreign_keys=[workspace_id])
