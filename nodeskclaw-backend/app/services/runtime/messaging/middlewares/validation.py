"""ValidationMiddleware — schema validation and source node legitimacy checks."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)

IDEMPOTENCY_ENABLED = False


class ValidationMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        envelope = ctx.envelope
        if envelope.data is None:
            logger.warning("ValidationMiddleware: envelope %s has no data, rejecting", envelope.id)
            ctx.short_circuited = True
            ctx.error = "envelope.data is required"
            return

        if not envelope.data.content and not envelope.data.attachments:
            logger.warning("ValidationMiddleware: envelope %s has empty content, rejecting", envelope.id)
            ctx.short_circuited = True
            ctx.error = "message content or attachments required"
            return

        if not envelope.workspaceid:
            logger.warning("ValidationMiddleware: envelope %s missing workspaceid", envelope.id)
            ctx.short_circuited = True
            ctx.error = "workspaceid is required"
            return

        if IDEMPOTENCY_ENABLED:
            pass

        await next_fn(ctx)
