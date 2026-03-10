"""MessagePipeline — middleware pipeline for processing MessageEnvelopes."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from app.services.runtime.messaging.envelope import MessageEnvelope

logger = logging.getLogger(__name__)

NextFn = Callable[["PipelineContext"], Coroutine[Any, Any, None]]


@dataclass
class PipelineContext:
    envelope: MessageEnvelope
    workspace_id: str = ""
    topology_cache: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    delivery_plan: Any = None
    short_circuited: bool = False
    error: str | None = None
    extra: dict = field(default_factory=dict)


class MessageMiddleware:
    """Base class for message middleware. Override `process` to implement."""

    async def process(
        self,
        ctx: PipelineContext,
        next_fn: NextFn,
    ) -> None:
        await next_fn(ctx)


class MessagePipeline:
    def __init__(self) -> None:
        self._middlewares: list[MessageMiddleware] = []

    def use(self, middleware: MessageMiddleware) -> MessagePipeline:
        self._middlewares.append(middleware)
        return self

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        index = 0
        middlewares = self._middlewares

        async def run(context: PipelineContext) -> None:
            nonlocal index
            if context.short_circuited:
                return
            if index < len(middlewares):
                mw = middlewares[index]
                index += 1
                try:
                    await mw.process(context, run)
                except Exception as e:
                    logger.error(
                        "Middleware %s failed: %s",
                        type(mw).__name__, e, exc_info=True,
                    )
                    context.error = str(e)
            # terminal: no more middlewares

        await run(ctx)
        return ctx
