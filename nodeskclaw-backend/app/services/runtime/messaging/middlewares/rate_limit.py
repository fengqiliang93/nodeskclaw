"""RateLimitMiddleware — per-node rate limiting (optional, EE feature)."""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)

DEFAULT_RATE = 60
DEFAULT_WINDOW_S = 60


class RateLimitMiddleware(MessageMiddleware):
    def __init__(self, rate: int = DEFAULT_RATE, window_s: int = DEFAULT_WINDOW_S) -> None:
        self._rate = rate
        self._window_s = window_s
        self._counters: dict[str, list[float]] = defaultdict(list)

    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        sender_id = ""
        if ctx.envelope.data:
            sender_id = ctx.envelope.data.sender.id

        if sender_id:
            now = time.monotonic()
            timestamps = self._counters[sender_id]
            cutoff = now - self._window_s
            timestamps[:] = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self._rate:
                logger.warning("RateLimit exceeded for sender %s", sender_id)
                ctx.short_circuited = True
                ctx.error = "rate_limit_exceeded"
                return

            timestamps.append(now)

        await next_fn(ctx)
