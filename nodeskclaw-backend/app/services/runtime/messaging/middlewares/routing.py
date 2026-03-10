"""RoutingMiddleware — generates a DeliveryPlan by invoking the topology-based corridor router."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.delivery_plan import DeliveryPlan, DeliveryTarget
from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


async def _resolve_targets_by_name(
    names: list[str], workspace_id: str, db,
) -> list[DeliveryTarget]:
    """Resolve target names (display_name or node_id) to DeliveryTarget objects."""
    from app.models.base import not_deleted
    from app.models.node_card import NodeCard
    from app.services.runtime.registries.node_type_registry import NODE_TYPE_REGISTRY
    from sqlalchemy import or_, select

    targets: list[DeliveryTarget] = []
    for name in names:
        stmt = select(NodeCard).where(
            NodeCard.workspace_id == workspace_id,
            not_deleted(NodeCard),
            or_(NodeCard.name == name, NodeCard.node_id == name),
        )
        result = await db.execute(stmt)
        card = result.scalar_one_or_none()
        if card is None:
            logger.warning("Routing: target '%s' not found in workspace %s", name, workspace_id)
            continue

        type_spec = NODE_TYPE_REGISTRY.get(card.node_type)
        transport = type_spec.transport if type_spec else ""
        targets.append(DeliveryTarget(
            node_id=card.node_id,
            node_type=card.node_type,
            transport=transport or "",
        ))
    return targets


async def _resolve_broadcast(workspace_id: str, db) -> list[DeliveryTarget]:
    """BFS from blackboard (0,0) to find all reachable endpoints via corridor topology."""
    from app.services.corridor_router import get_blackboard_audience, has_any_connections
    from app.services.runtime.registries.node_type_registry import NODE_TYPE_REGISTRY

    has_topo = await has_any_connections(workspace_id, db)

    if has_topo:
        endpoints = await get_blackboard_audience(workspace_id, db)
        targets: list[DeliveryTarget] = []
        for ep in endpoints:
            type_spec = NODE_TYPE_REGISTRY.get(ep.endpoint_type)
            transport = type_spec.transport if type_spec else ""
            targets.append(DeliveryTarget(
                node_id=ep.entity_id,
                node_type=ep.endpoint_type,
                transport=transport or "",
            ))
        return targets

    from app.models.base import not_deleted
    from app.models.node_card import NodeCard
    from sqlalchemy import select

    stmt = select(NodeCard).where(
        NodeCard.workspace_id == workspace_id,
        not_deleted(NodeCard),
        NodeCard.node_type.in_(["agent", "human"]),
    )
    result = await db.execute(stmt)
    targets = []
    for card in result.scalars().all():
        type_spec = NODE_TYPE_REGISTRY.get(card.node_type)
        transport = type_spec.transport if type_spec else ""
        targets.append(DeliveryTarget(
            node_id=card.node_id,
            node_type=card.node_type,
            transport=transport or "",
        ))
    return targets


class RoutingMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        data = ctx.envelope.data
        if data is None:
            await next_fn(ctx)
            return

        db = ctx.db

        if data.routing.targets:
            mode = "unicast" if len(data.routing.targets) == 1 else "multicast"
            resolved: list[DeliveryTarget] = []
            if db is not None:
                resolved = await _resolve_targets_by_name(
                    data.routing.targets, ctx.workspace_id, db,
                )
            ctx.delivery_plan = DeliveryPlan(
                targets=data.routing.targets,
                resolved_targets=resolved,
                mode=mode,
                workspace_id=ctx.workspace_id,
            )
        else:
            resolved = []
            if db is not None:
                resolved = await _resolve_broadcast(ctx.workspace_id, db)

            sender_id = data.sender.instance_id or data.sender.id
            resolved = [t for t in resolved if t.node_id != sender_id]

            ctx.delivery_plan = DeliveryPlan(
                targets=[],
                resolved_targets=resolved,
                mode="broadcast",
                workspace_id=ctx.workspace_id,
            )

        logger.debug(
            "Routing: mode=%s resolved=%d targets for envelope %s",
            ctx.delivery_plan.mode,
            len(ctx.delivery_plan.resolved_targets),
            ctx.envelope.id,
        )

        await next_fn(ctx)
