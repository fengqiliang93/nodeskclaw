"""SemanticMiddleware — five-dimensional message classification and @mention processing."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.envelope import IntentType, Priority, Urgency
from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class SemanticMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        data = ctx.envelope.data
        if data is None:
            await next_fn(ctx)
            return

        has_mention = bool(data.mentions)
        has_delay = data.scheduling.delay_seconds > 0

        if has_mention:
            data.extensions["has_mentions"] = True
            data.extensions["mention_targets"] = data.mentions
            data.priority = Priority.CRITICAL
            data.scheduling.urgency = Urgency.IMMEDIATE
        elif has_delay:
            data.scheduling.urgency = Urgency.SCHEDULED
        elif data.intent == IntentType.COLLABORATE:
            if data.priority == Priority.BACKGROUND:
                data.priority = Priority.NORMAL
        else:
            if data.scheduling.urgency not in (Urgency.IMMEDIATE, Urgency.DEFERRED, Urgency.SCHEDULED):
                data.scheduling.urgency = Urgency.NORMAL

        if data.routing.priority is not None:
            data.priority = data.routing.priority

        ctx.extra["classified"] = True
        await next_fn(ctx)
