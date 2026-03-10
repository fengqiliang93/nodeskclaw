"""MetricsMiddleware — collects message processing metrics (OpenTelemetry integration point)."""

from __future__ import annotations

import logging
import time

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class MetricsMiddleware(MessageMiddleware):
    def __init__(self) -> None:
        self._total_messages = 0
        self._total_errors = 0
        self._total_latency_ms = 0.0

    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        start = time.monotonic()
        self._total_messages += 1

        await next_fn(ctx)

        elapsed_ms = (time.monotonic() - start) * 1000
        self._total_latency_ms += elapsed_ms
        ctx.metrics["pipeline_latency_ms"] = elapsed_ms

        if ctx.error:
            self._total_errors += 1

    @property
    def stats(self) -> dict:
        return {
            "total_messages": self._total_messages,
            "total_errors": self._total_errors,
            "avg_latency_ms": (
                self._total_latency_ms / self._total_messages
                if self._total_messages > 0 else 0
            ),
        }
