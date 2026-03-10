"""NodeTypeDefinition — registry-backed node type declarations for the runtime platform."""

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class NodeTypeDefinition(BaseModel):
    __tablename__ = "node_type_definitions"
    __table_args__ = (
        Index(
            "uq_node_type_definitions_type_id",
            "type_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    type_id: Mapped[str] = mapped_column(String(64), nullable=False)
    routing_role: Mapped[str] = mapped_column(String(32), nullable=False)
    transport: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    hooks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    propagates: Mapped[bool] = mapped_column(default=False, nullable=False)
    consumes: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_addressable: Mapped[bool] = mapped_column(default=True, nullable=False)
    can_originate: Mapped[bool] = mapped_column(default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
