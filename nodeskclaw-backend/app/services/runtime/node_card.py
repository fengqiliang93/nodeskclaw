"""NodeCard business logic — CRUD, queries, and conversions for the unified node representation."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.node_card import NodeCard

logger = logging.getLogger(__name__)


async def create_node_card(
    db: AsyncSession,
    *,
    node_type: str,
    node_id: str,
    workspace_id: str,
    hex_q: int,
    hex_r: int,
    name: str = "",
    status: str = "active",
    description: str | None = None,
    tags: list | None = None,
    metadata: dict | None = None,
) -> NodeCard:
    card = NodeCard(
        id=str(uuid.uuid4()),
        node_type=node_type,
        node_id=node_id,
        workspace_id=workspace_id,
        hex_q=hex_q,
        hex_r=hex_r,
        name=name,
        status=status,
        description=description,
        tags=tags,
        metadata_=metadata,
    )
    db.add(card)
    return card


async def get_node_card(
    db: AsyncSession, *, node_id: str, workspace_id: str,
) -> NodeCard | None:
    result = await db.execute(
        select(NodeCard).where(
            NodeCard.node_id == node_id,
            NodeCard.workspace_id == workspace_id,
            not_deleted(NodeCard),
        )
    )
    return result.scalar_one_or_none()


async def get_node_card_by_hex(
    db: AsyncSession, *, workspace_id: str, hex_q: int, hex_r: int,
) -> NodeCard | None:
    result = await db.execute(
        select(NodeCard).where(
            NodeCard.workspace_id == workspace_id,
            NodeCard.hex_q == hex_q,
            NodeCard.hex_r == hex_r,
            not_deleted(NodeCard),
        )
    )
    return result.scalar_one_or_none()


async def list_node_cards(
    db: AsyncSession, *, workspace_id: str, node_type: str | None = None,
) -> list[NodeCard]:
    stmt = select(NodeCard).where(
        NodeCard.workspace_id == workspace_id,
        not_deleted(NodeCard),
    )
    if node_type is not None:
        stmt = stmt.where(NodeCard.node_type == node_type)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_node_card(
    db: AsyncSession,
    card: NodeCard,
    **kwargs,
) -> NodeCard:
    for key, value in kwargs.items():
        if key == "metadata":
            setattr(card, "metadata_", value)
        elif hasattr(card, key):
            setattr(card, key, value)
    return card


async def soft_delete_node_card(
    db: AsyncSession, *, node_id: str, workspace_id: str,
) -> bool:
    card = await get_node_card(db, node_id=node_id, workspace_id=workspace_id)
    if card is None:
        return False
    card.soft_delete()
    return True


async def get_all_node_cards_map(
    db: AsyncSession, *, workspace_id: str,
) -> dict[tuple[int, int], NodeCard]:
    cards = await list_node_cards(db, workspace_id=workspace_id)
    return {(c.hex_q, c.hex_r): c for c in cards}
