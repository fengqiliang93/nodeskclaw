"""Portal ingestion — converts Portal HTTP requests into MessageEnvelopes."""

from __future__ import annotations

from app.services.runtime.messaging.envelope import (
    IntentType,
    MessageData,
    MessageEnvelope,
    MessageSender,
    Priority,
    SenderType,
)


def build_portal_envelope(
    *,
    workspace_id: str,
    user_id: str,
    user_name: str,
    content: str,
    mentions: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> MessageEnvelope:
    return MessageEnvelope(
        source=f"portal/user/{user_id}",
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
            mentions=mentions or [],
            attachments=attachments or [],
            priority=Priority.NORMAL,
        ),
    )
