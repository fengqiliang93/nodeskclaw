"""Instance failure recovery — heartbeat monitoring and stale connection cleanup.

Runs as a periodic background task during lifespan:
  - Scans sse_connections for heartbeat timeouts (30s threshold)
  - Soft-deletes stale connections
  - PG transaction rollback auto-releases FOR UPDATE locks on message_queue
  - Surviving clients reconnect and get assigned to live backend instances
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.runtime import sse_registry

logger = logging.getLogger(__name__)

SCAN_INTERVAL_S = 30


async def run_heartbeat_scanner(session_factory: Any) -> None:
    """Long-running coroutine that periodically cleans up stale SSE connections."""
    logger.info("Heartbeat scanner started (interval=%ds)", SCAN_INTERVAL_S)
    while True:
        try:
            await asyncio.sleep(SCAN_INTERVAL_S)
            async with session_factory() as db:
                cleaned = await sse_registry.cleanup_stale_connections(db)
                if cleaned:
                    await db.commit()
        except asyncio.CancelledError:
            logger.info("Heartbeat scanner cancelled")
            break
        except Exception:
            logger.exception("Heartbeat scanner error")


async def shutdown_cleanup(session_factory: Any) -> None:
    """Called during graceful shutdown to unregister this backend's connections."""
    try:
        async with session_factory() as db:
            cleaned = await sse_registry.cleanup_backend_connections(db)
            await db.commit()
            logger.info("Shutdown cleanup: removed %d connections for this backend", cleaned)
    except Exception:
        logger.exception("Shutdown cleanup failed")
