"""DingTalk ingestion — converts DingTalk Stream/Webhook events into MessageEnvelopes."""

from __future__ import annotations

from app.services.runtime.messaging.envelope import (
    IntentType,
    MessageData,
    MessageEnvelope,
    MessageSender,
    Priority,
    SenderType,
)


def build_dingtalk_envelope(
    *,
    workspace_id: str,
    user_id: str,
    user_name: str,
    content: str,
    conversation_id: str = "",
    dingtalk_message_id: str = "",
    is_group: bool = False,
) -> MessageEnvelope:
    source = f"dingtalk/{'group' if is_group else 'user'}/{user_id}"
    extensions: dict = {}
    if dingtalk_message_id:
        extensions["dingtalk_message_id"] = dingtalk_message_id
    if conversation_id:
        extensions["dingtalk_conversation_id"] = conversation_id
    if is_group:
        extensions["dingtalk_is_group"] = True

    return MessageEnvelope(
        source=source,
        type="deskclaw.msg.v1.chat",
        workspaceid=workspace_id,
        data=MessageData(
            sender=MessageSender(
                id=user_id,
                type=SenderType.EXTERNAL,
                name=user_name,
            ),
            intent=IntentType.CHAT,
            content=content,
            priority=Priority.NORMAL,
            extensions=extensions,
        ),
    )


def parse_dingtalk_callback_event(payload: dict) -> dict | None:
    """Parse a DingTalk Stream callback event into a normalized dict.

    Returns None if the payload is not a recognizable message event.

    Expected DingTalk Stream callback structure:
    {
        "conversationId": "...",
        "atUsers": [...],
        "chatbotCorpId": "...",
        "chatbotUserId": "...",
        "msgId": "...",
        "senderNick": "...",
        "isAdmin": false,
        "senderStaffId": "...",
        "sessionWebhookExpiredTime": ...,
        "createAt": ...,
        "senderCorpId": "...",
        "conversationType": "1" (single) | "2" (group),
        "sessionWebhook": "...",
        "text": {"content": "..."},
        "msgtype": "text",
    }
    """
    msg_type = payload.get("msgtype")
    if not msg_type:
        return None

    text_obj = payload.get("text", {})
    content = text_obj.get("content", "").strip() if isinstance(text_obj, dict) else ""

    conversation_type = payload.get("conversationType", "1")
    is_group = conversation_type == "2"

    return {
        "sender_staff_id": payload.get("senderStaffId", ""),
        "sender_nick": payload.get("senderNick", ""),
        "conversation_id": payload.get("conversationId", ""),
        "msg_id": payload.get("msgId", ""),
        "content": content,
        "is_group": is_group,
        "msg_type": msg_type,
        "session_webhook": payload.get("sessionWebhook", ""),
    }
