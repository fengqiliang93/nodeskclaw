"""AuditMiddleware — records all message operations to the event sourcing log."""

from __future__ import annotations

import logging

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class AuditMiddleware(MessageMiddleware):
    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        logger.debug(
            "AuditMiddleware: message %s entering pipeline (workspace=%s)",
            ctx.envelope.id, ctx.workspace_id,
        )

        await next_fn(ctx)

        if ctx.error:
            logger.info(
                "AuditMiddleware: message %s failed: %s",
                ctx.envelope.id, ctx.error,
            )
        else:
            logger.debug(
                "AuditMiddleware: message %s completed pipeline",
                ctx.envelope.id,
            )
