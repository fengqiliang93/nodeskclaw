"""Cron ingestion — wraps ScheduleRunner outputs into MessageEnvelopes."""

from __future__ import annotations

from app.services.runtime.messaging.envelope import (
    IntentType,
    MessageData,
    MessageEnvelope,
    MessageSender,
    Priority,
    SenderType,
)


def build_cron_envelope(
    *,
    workspace_id: str,
    schedule_id: str,
    schedule_name: str,
    message_template: str,
) -> MessageEnvelope:
    return MessageEnvelope(
        source=f"cron/{schedule_id}",
        type="deskclaw.msg.v1.notify",
        workspaceid=workspace_id,
        data=MessageData(
            sender=MessageSender(
                id=schedule_id,
                type=SenderType.CRON,
                name=schedule_name,
            ),
            intent=IntentType.NOTIFY,
            content=message_template,
            priority=Priority.NORMAL,
        ),
    )
