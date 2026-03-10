"""RateLimitMiddleware — per-sender rate limiting with receiver-side support.

Sender-side check runs in the middleware pipeline (before routing).
Receiver-side check is exposed as a helper for TransportMiddleware to call
per-target after the DeliveryPlan is generated.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)

DEFAULT_SENDER_RATE = 60
DEFAULT_RECEIVER_RATE = 120
DEFAULT_WINDOW_S = 60


_receiver_counters: dict[str, list[float]] = defaultdict(list)


def check_receiver_rate(
    target_node_id: str,
    *,
    rate: int = DEFAULT_RECEIVER_RATE,
    window_s: int = DEFAULT_WINDOW_S,
) -> bool:
    """Return True if the receiver can accept another message, False if throttled."""
    now = time.monotonic()
    timestamps = _receiver_counters[target_node_id]
    cutoff = now - window_s
    timestamps[:] = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= rate:
        return False

    timestamps.append(now)
    return True


class RateLimitMiddleware(MessageMiddleware):
    def __init__(self, rate: int = DEFAULT_SENDER_RATE, window_s: int = DEFAULT_WINDOW_S) -> None:
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
