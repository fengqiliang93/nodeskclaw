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


@router.get("/{workspace_id}/messages/{message_id}/reconstruct")
async def reconstruct_message_state(
    workspace_id: str, message_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    """Reconstruct full message lifecycle from event log."""
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    result = await db.execute(
        select(EventLog)
        .where(
            EventLog.message_id == message_id,
            EventLog.workspace_id == workspace_id,
        )
        .order_by(EventLog.created_at.asc())
    )
    events = result.scalars().all()

    timeline = []
    state = {
        "message_id": message_id,
        "current_status": "unknown",
        "created_at": None,
        "delivered_to": [],
        "failed_targets": [],
        "retried_targets": [],
        "dead_lettered_targets": [],
    }

    for e in events:
        entry = {
            "event_type": e.event_type,
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "data": e.data,
        }
        timeline.append(entry)

        if e.event_type == "message_created":
            state["current_status"] = "created"
            state["created_at"] = e.created_at.isoformat() if e.created_at else None
        elif e.event_type == "message_routed":
            state["current_status"] = "routed"
        elif e.event_type == "message_delivering":
            state["current_status"] = "delivering"
        elif e.event_type == "message_delivered":
            state["current_status"] = "delivered"
            if e.data and e.data.get("delivered_to"):
                state["delivered_to"].extend(e.data["delivered_to"])
        elif e.event_type == "message_delivery_failed":
            state["current_status"] = "failed"
            if e.data and e.data.get("failed_targets"):
                state["failed_targets"].extend(e.data["failed_targets"])
        elif e.event_type == "message_retried":
            if e.data and e.data.get("target_node_id"):
                state["retried_targets"].append(e.data["target_node_id"])
        elif e.event_type == "message_dead_lettered":
            if e.data and e.data.get("target_node_id"):
                state["dead_lettered_targets"].append(e.data["target_node_id"])
        elif e.event_type == "message_pipeline_error":
            state["current_status"] = "error"

    return _ok({
        "state": state,
        "timeline": timeline,
        "event_count": len(timeline),
    })


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


@router.put("/{workspace_id}/nodes/{node_id}/card")
async def update_node_card(
    workspace_id: str, node_id: str,
    body: dict,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    from app.services.runtime import node_card as nc_service

    card = await nc_service.get_node_card(db, node_id=node_id, workspace_id=workspace_id)
    if card is None:
        return {"code": 40430, "message": "NodeCard not found", "data": None}

    allowed = {"name", "description", "tags", "status", "metadata"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if updates:
        await nc_service.update_node_card(db, card, **updates)
        await db.commit()
    return _ok({"node_id": card.node_id, "updated": list(updates.keys())})


@router.post("/{workspace_id}/nodes/{node_id}/messages")
async def post_node_message(
    workspace_id: str, node_id: str,
    body: dict,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    """Type-agnostic node messaging endpoint."""
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    from app.services.runtime.messaging.bus import message_bus
    from app.services.runtime.messaging.envelope import (
        IntentType,
        MessageData,
        MessageEnvelope,
        MessageRouting,
        MessageSender,
        Priority,
        SenderType,
    )

    content = body.get("content", "")
    target = body.get("target", "")
    targets = [target] if target else []

    envelope = MessageEnvelope(
        source=f"api/node/{node_id}",
        type="deskclaw.msg.v1.collaborate",
        workspaceid=workspace_id,
        data=MessageData(
            sender=MessageSender(
                id=node_id,
                type=SenderType(body.get("sender_type", "agent")),
                name=body.get("sender_name", ""),
                instance_id=node_id,
            ),
            intent=IntentType(body.get("intent", "collaborate")),
            content=content,
            priority=Priority(body.get("priority", "normal")),
            routing=MessageRouting(
                mode="unicast" if targets else "broadcast",
                targets=targets,
            ),
        ),
    )

    result = await message_bus.publish(envelope, db=db)
    await db.commit()
    return _ok({
        "envelope_id": envelope.id,
        "trace_id": envelope.traceid,
        "error": result.error,
    })


@router.get("/{workspace_id}/nodes/types")
async def list_node_types(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    from app.services.runtime.registries.node_type_registry import NODE_TYPE_REGISTRY

    types = NODE_TYPE_REGISTRY.all_types()
    return _ok([
        {
            "type_id": t.type_id,
            "routing_role": t.routing_role.value,
            "transport": t.transport,
            "propagates": t.propagates,
            "consumes": t.consumes,
            "is_addressable": t.is_addressable,
            "can_originate": t.can_originate,
            "description": t.description,
        }
        for t in types
    ])


@router.get("/{workspace_id}/messages/alerts")
async def get_active_alerts(
    workspace_id: str,
    org_ctx=Depends(get_current_org), db: AsyncSession = Depends(get_db),
):
    user, org = org_ctx
    await wm_service.check_workspace_member(workspace_id, user, db)

    open_circuits = await db.execute(
        select(CircuitState).where(
            CircuitState.workspace_id == workspace_id,
            CircuitState.state.in_(["open", "half_open"]),
            not_deleted(CircuitState),
        )
    )
    circuit_alerts = [
        {
            "type": "circuit_breaker",
            "node_id": cs.node_id,
            "state": cs.state,
            "failure_count": cs.failure_count,
            "opened_at": cs.opened_at.isoformat() if cs.opened_at else None,
        }
        for cs in open_circuits.scalars().all()
    ]

    dl_count_q = await db.execute(
        select(func.count(DeadLetter.id)).where(
            DeadLetter.workspace_id == workspace_id,
            DeadLetter.recovered_at.is_(None),
            not_deleted(DeadLetter),
        )
    )
    dl_count = dl_count_q.scalar_one_or_none() or 0

    pending_q = await db.execute(
        select(func.count(MessageQueueItem.id)).where(
            MessageQueueItem.workspace_id == workspace_id,
            MessageQueueItem.status.in_(["pending", "retrying"]),
            not_deleted(MessageQueueItem),
        )
    )
    pending_count = pending_q.scalar_one_or_none() or 0

    alerts = circuit_alerts
    if dl_count > 0:
        alerts.append({"type": "dead_letters", "count": dl_count})
    if pending_count > 10:
        alerts.append({"type": "queue_backlog", "pending_count": pending_count})

    return _ok(alerts)
