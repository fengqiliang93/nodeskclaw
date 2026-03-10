"""SemanticMiddleware — five-dimensional message classification and @mention processing."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.envelope import Priority, Urgency
from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class SemanticMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        data = ctx.envelope.data
        if data is None:
            await next_fn(ctx)
            return

        if data.mentions:
            data.extensions["has_mentions"] = True
            data.extensions["mention_targets"] = data.mentions
            if data.priority == Priority.BACKGROUND:
                data.priority = Priority.NORMAL
            if data.scheduling.urgency == Urgency.DEFERRED:
                data.scheduling.urgency = Urgency.NORMAL

        ctx.extra["classified"] = True
        await next_fn(ctx)
