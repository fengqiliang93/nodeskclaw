"""Observability API — message tracing, metrics, dead letters, circuit breakers, event sourcing."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_org, get_db
from app.models.base import not_deleted
from app.models.circuit_state import CircuitState
from app.models.dead_letter import DeadLetter
from app.models.event_log import EventLog
from app.models.message_queue import MessageQueueItem
from app.models.node_card import NodeCard
from app.services import workspace_member_service as wm_service
from app.services.runtime.messaging import queue as queue_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


@router.get("/{workspace_id}/messages/trace/{trace_id}")
async def get_message_trace(
    workspace_id: str, trace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    result = await db.execute(
        select(EventLog)
        .where(EventLog.trace_id == trace_id, EventLog.workspace_id == workspace_id)
        .order_by(EventLog.created_at.asc())
    )
    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "message_id": e.message_id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "data": e.data,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]
    return _ok(events)


@router.get("/{workspace_id}/messages/metrics")
async def get_workspace_metrics(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    queue_count = await db.execute(
        select(func.count()).select_from(MessageQueueItem).where(
            MessageQueueItem.workspace_id == workspace_id,
            MessageQueueItem.status.in_(["pending", "retrying"]),
            not_deleted(MessageQueueItem),
        )
    )
    dead_count = await db.execute(
        select(func.count()).select_from(DeadLetter).where(
            DeadLetter.workspace_id == workspace_id,
            DeadLetter.recovered_at.is_(None),
            not_deleted(DeadLetter),
        )
    )

    return _ok({
        "queue_depth": queue_count.scalar() or 0,
        "dead_letter_count": dead_count.scalar() or 0,
    })


@router.get("/{workspace_id}/messages/metrics/nodes/{node_id}")
async def get_node_metrics(
    workspace_id: str, node_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    depth = await queue_service.get_queue_depth(db, node_id)
    bp_level = queue_service.get_backpressure_level(depth)

    circuit_q = await db.execute(
        select(CircuitState).where(
            CircuitState.node_id == node_id,
            CircuitState.workspace_id == workspace_id,
            not_deleted(CircuitState),
        )
    )
    cs = circuit_q.scalar_one_or_none()

    return _ok({
        "node_id": node_id,
        "queue_depth": depth,
        "backpressure_level": bp_level,
        "circuit_state": cs.state if cs else "closed",
        "failure_count": cs.failure_count if cs else 0,
    })


@router.get("/{workspace_id}/messages/heatmap")
async def get_message_heatmap(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    result = await db.execute(
        select(
            EventLog.target_node_id,
            func.count(EventLog.id).label("count"),
        )
        .where(
            EventLog.workspace_id == workspace_id,
            EventLog.event_type == "message_delivered",
        )
        .group_by(EventLog.target_node_id)
    )
    heatmap = [
        {"node_id": row.target_node_id, "message_count": row.count}
        for row in result.all()
    ]
    return _ok(heatmap)


@router.get("/{workspace_id}/messages/dead-letters")
async def list_dead_letters(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    result = await db.execute(
        select(DeadLetter)
        .where(
            DeadLetter.workspace_id == workspace_id,
            DeadLetter.recovered_at.is_(None),
            not_deleted(DeadLetter),
        )
        .order_by(DeadLetter.created_at.desc())
        .limit(100)
    )
    items = [
        {
            "id": dl.id,
            "message_id": dl.message_id,
            "target_node_id": dl.target_node_id,
            "attempt_count": dl.attempt_count,
            "last_error": dl.last_error,
            "created_at": dl.created_at.isoformat() if dl.created_at else None,
        }
        for dl in result.scalars().all()
    ]
    return _ok(items)


@router.post("/{workspace_id}/messages/dead-letters/{dl_id}/retry")
async def retry_dead_letter(
    workspace_id: str, dl_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    recovered = await queue_service.recover_dead_letter(db, dl_id, user.id)
    if not recovered:
        return _ok(message="dead letter not found or already recovered")
    await db.commit()
    return _ok(message="dead letter re-queued")


@router.get("/{workspace_id}/messages/circuit-breakers")
async def list_circuit_breakers(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    result = await db.execute(
        select(CircuitState)
        .where(
            CircuitState.workspace_id == workspace_id,
            not_deleted(CircuitState),
        )
    )
    items = [
        {
            "node_id": cs.node_id,
            "state": cs.state,
            "failure_count": cs.failure_count,
            "success_count": cs.success_count,
            "last_failure_at": cs.last_failure_at.isoformat() if cs.last_failure_at else None,
            "opened_at": cs.opened_at.isoformat() if cs.opened_at else None,
        }
        for cs in result.scalars().all()
    ]
    return _ok(items)


@router.get("/{workspace_id}/messages/events")
async def list_events(
    workspace_id: str,
    event_type: str | None = Query(None),
    limit: int = Query(100, le=500),
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    stmt = (
        select(EventLog)
        .where(EventLog.workspace_id == workspace_id)
        .order_by(EventLog.created_at.desc())
        .limit(limit)
    )
    if event_type:
        stmt = stmt.where(EventLog.event_type == event_type)
    result = await db.execute(stmt)
    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "message_id": e.message_id,
            "source_node_id": e.source_node_id,
            "target_node_id": e.target_node_id,
            "trace_id": e.trace_id,
            "data": e.data,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]
    return _ok(events)


@router.get("/{workspace_id}/messages/queue-stats")
async def get_queue_stats(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    status_counts = await db.execute(
        select(
            MessageQueueItem.status,
            func.count(MessageQueueItem.id).label("count"),
        )
        .where(
            MessageQueueItem.workspace_id == workspace_id,
            not_deleted(MessageQueueItem),
        )
        .group_by(MessageQueueItem.status)
    )
    stats = {row.status: row.count for row in status_counts.all()}
    return _ok(stats)


@router.get("/{workspace_id}/nodes/{node_id}/card")
async def get_node_card(
    workspace_id: str, node_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    result = await db.execute(
        select(NodeCard).where(
            NodeCard.node_id == node_id,
            NodeCard.workspace_id == workspace_id,
            not_deleted(NodeCard),
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        return _ok(None)
    return _ok({
        "id": card.id,
        "node_type": card.node_type,
        "node_id": card.node_id,
        "workspace_id": card.workspace_id,
        "hex_q": card.hex_q,
        "hex_r": card.hex_r,
        "name": card.name,
        "status": card.status,
        "description": card.description,
        "tags": card.tags,
        "metadata": card.metadata_,
    })


@router.get("/{workspace_id}/nodes/discover")
async def discover_nodes(
    workspace_id: str,
    node_type: str | None = Query(None),
    tag: str | None = Query(None),
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)
    stmt = select(NodeCard).where(
        NodeCard.workspace_id == workspace_id,
        not_deleted(NodeCard),
    )
    if node_type:
        stmt = stmt.where(NodeCard.node_type == node_type)
    result = await db.execute(stmt)
    cards = [
        {
            "node_id": c.node_id,
            "node_type": c.node_type,
            "name": c.name,
            "status": c.status,
            "description": c.description,
            "tags": c.tags,
            "hex_q": c.hex_q,
            "hex_r": c.hex_r,
        }
        for c in result.scalars().all()
    ]
    if tag:
        cards = [c for c in cards if c.get("tags") and tag in c["tags"]]
    return _ok(cards)
