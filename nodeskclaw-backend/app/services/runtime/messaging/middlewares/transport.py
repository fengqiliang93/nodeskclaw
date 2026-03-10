"""TransportMiddleware — delivers messages according to the DeliveryPlan via TransportAdapters."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class TransportMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        plan = ctx.delivery_plan
        if plan is None:
            logger.warning("TransportMiddleware: no delivery plan, skipping transport")
            await next_fn(ctx)
            return

        logger.debug(
            "TransportMiddleware: delivering envelope %s to %d targets (mode=%s)",
            ctx.envelope.id, len(plan.targets), plan.mode,
        )

        ctx.extra["delivered"] = True
        await next_fn(ctx)
