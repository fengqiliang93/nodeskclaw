"""WorkspaceAgent — many-to-many junction between Instance and Workspace."""

from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WorkspaceAgent(BaseModel):
    __tablename__ = "workspace_agents"
    __table_args__ = (
        Index(
            "uq_workspace_agent",
            "workspace_id",
            "instance_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hex_q: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hex_r: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    theme_color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    instance = relationship("Instance", foreign_keys=[instance_id])
