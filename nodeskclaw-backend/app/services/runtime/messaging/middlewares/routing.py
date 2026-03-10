"""RoutingMiddleware — generates a DeliveryPlan by invoking the topology-based corridor router."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class RoutingMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        data = ctx.envelope.data
        if data is None:
            await next_fn(ctx)
            return

        from app.services.runtime.messaging.delivery_plan import DeliveryPlan

        if data.routing.targets:
            ctx.delivery_plan = DeliveryPlan(
                targets=data.routing.targets,
                mode="unicast" if len(data.routing.targets) == 1 else "multicast",
                workspace_id=ctx.workspace_id,
            )
        else:
            ctx.delivery_plan = DeliveryPlan(
                targets=[],
                mode="broadcast",
                workspace_id=ctx.workspace_id,
                needs_topology_resolution=True,
            )

        await next_fn(ctx)
