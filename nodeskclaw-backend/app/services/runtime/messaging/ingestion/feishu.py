"""Feishu ingestion — converts Feishu Webhook/WebSocket events into MessageEnvelopes."""

from __future__ import annotations

from app.services.runtime.messaging.envelope import (
    IntentType,
    MessageData,
    MessageEnvelope,
    MessageSender,
    Priority,
    SenderType,
)


def build_feishu_envelope(
    *,
    workspace_id: str,
    user_id: str,
    user_name: str,
    content: str,
    feishu_message_id: str = "",
) -> MessageEnvelope:
    return MessageEnvelope(
        source=f"feishu/user/{user_id}",
        type="deskclaw.msg.v1.chat",
        workspaceid=workspace_id,
        data=MessageData(
            sender=MessageSender(
                id=user_id,
                type=SenderType.USER,
                name=user_name,
            ),
            intent=IntentType.CHAT,
            content=content,
            priority=Priority.NORMAL,
            extensions={"feishu_message_id": feishu_message_id} if feishu_message_id else {},
        ),
    )
