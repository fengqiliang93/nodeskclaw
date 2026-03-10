"""ContentFilterMiddleware — enterprise content compliance filtering (EE feature).

CE version is a pass-through. EE overrides via FeatureGate to inject
actual content policy checks (PII, sensitive keywords, regulatory compliance).
"""

from __future__ import annotations

import logging

from app.services.runtime.messaging.pipeline import MessageMiddleware, NextFn, PipelineContext

logger = logging.getLogger(__name__)


class ContentFilterMiddleware(MessageMiddleware):
    """CE stub: no-op content filter. EE replaces this via hook registration."""

    async def process(self, ctx: PipelineContext, next_fn: NextFn) -> None:
        await next_fn(ctx)
