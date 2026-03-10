"""MessageSchema — versioned message type schema definitions."""

from sqlalchemy import Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MessageSchema(BaseModel):
    __tablename__ = "message_schemas"
    __table_args__ = (
        Index(
            "uq_message_schema_type_version",
            "type_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    type_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    schema_def: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
