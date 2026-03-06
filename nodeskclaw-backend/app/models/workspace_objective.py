"""WorkspaceObjective — OKR-style objective within a workspace blackboard.

Supports O -> KR hierarchy via `parent_id` and `obj_type`:
- obj_type='objective' (O): top-level strategic objective
- obj_type='key_result' (KR): measurable key result under an O
"""

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WorkspaceObjective(BaseModel):
    __tablename__ = "workspace_objectives"

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    obj_type: Mapped[str] = mapped_column(
        String(20), default="objective", nullable=False, index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspace_objectives.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    parent = relationship("WorkspaceObjective", remote_side="WorkspaceObjective.id", foreign_keys=[parent_id])
    children = relationship("WorkspaceObjective", back_populates="parent", foreign_keys=[parent_id])
