"""CircuitBreakerMiddleware — per-node circuit breaker protecting against cascading failures."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.circuit_state import CircuitState

logger = logging.getLogger(__name__)

FAILURE_THRESHOLD = 3
RECOVERY_TIMEOUT_S = 30
HALF_OPEN_MAX_PROBES = 1


async def get_circuit_state(
    db: AsyncSession, node_id: str, workspace_id: str,
) -> CircuitState | None:
    result = await db.execute(
        select(CircuitState).where(
            CircuitState.node_id == node_id,
            CircuitState.workspace_id == workspace_id,
            not_deleted(CircuitState),
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_circuit(
    db: AsyncSession, node_id: str, workspace_id: str,
) -> CircuitState:
    cs = await get_circuit_state(db, node_id, workspace_id)
    if cs:
        return cs
    cs = CircuitState(
        node_id=node_id,
        workspace_id=workspace_id,
        state="closed",
    )
    db.add(cs)
    await db.flush()
    return cs


async def record_success(
    db: AsyncSession, node_id: str, workspace_id: str,
) -> None:
    cs = await get_or_create_circuit(db, node_id, workspace_id)
    cs.success_count += 1
    cs.last_success_at = datetime.now(timezone.utc)

    if cs.state == "half_open":
        cs.state = "closed"
        cs.failure_count = 0
        logger.info("Circuit closed for node %s in workspace %s", node_id, workspace_id)

    await db.flush()


async def record_failure(
    db: AsyncSession, node_id: str, workspace_id: str,
) -> str:
    cs = await get_or_create_circuit(db, node_id, workspace_id)
    cs.failure_count += 1
    cs.last_failure_at = datetime.now(timezone.utc)

    if cs.state == "closed" and cs.failure_count >= FAILURE_THRESHOLD:
        cs.state = "open"
        cs.opened_at = datetime.now(timezone.utc)
        logger.warning("Circuit opened for node %s in workspace %s", node_id, workspace_id)
    elif cs.state == "half_open":
        cs.state = "open"
        cs.opened_at = datetime.now(timezone.utc)
        logger.warning("Circuit re-opened for node %s in workspace %s", node_id, workspace_id)

    await db.flush()
    return cs.state


def should_allow_request(cs: CircuitState) -> bool:
    if cs.state == "closed":
        return True
    if cs.state == "open":
        if cs.opened_at:
            elapsed = (datetime.now(timezone.utc) - cs.opened_at).total_seconds()
            if elapsed >= RECOVERY_TIMEOUT_S:
                return True
        return False
    if cs.state == "half_open":
        return True
    return False


async def try_half_open(
    db: AsyncSession, node_id: str, workspace_id: str,
) -> bool:
    cs = await get_or_create_circuit(db, node_id, workspace_id)
    if cs.state == "open" and cs.opened_at:
        elapsed = (datetime.now(timezone.utc) - cs.opened_at).total_seconds()
        if elapsed >= RECOVERY_TIMEOUT_S:
            cs.state = "half_open"
            cs.half_open_at = datetime.now(timezone.utc)
            await db.flush()
            logger.info("Circuit half-open for node %s in workspace %s", node_id, workspace_id)
            return True
    return False
