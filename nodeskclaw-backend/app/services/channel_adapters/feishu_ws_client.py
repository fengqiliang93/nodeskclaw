"""Feishu WebSocket long-connection client using lark-oapi SDK.

Receives im.message.receive_v1 events and routes them into the workspace,
reusing the same message handling logic as the HTTP webhook endpoint.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import TYPE_CHECKING

import lark_oapi as lark
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as LarkWSClient

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
_AT_MENTION_RE = re.compile(r'<at\b[^>]*\b(?:open_id|user_id)="([^"]+)"[^>]*>', re.IGNORECASE)


def _coerce_allowlist(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list | tuple | set):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return set()
        if text[:1] in {"[", "{"}:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return {str(item).strip() for item in parsed if str(item).strip()}
        if "," in text:
            return {part.strip() for part in text.split(",") if part.strip()}
        return {text}
    return {str(value).strip()} if str(value).strip() else set()


def _allowlist_matches(allowlist: set[str], value: str) -> bool:
    return "*" in allowlist or value in allowlist


def _extract_mention_tokens(message: dict) -> set[str]:
    tokens: set[str] = set()
    mentions = message.get("mentions")
    if isinstance(mentions, list):
        for item in mentions:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if key:
                tokens.add(key.lower())
            raw_id = item.get("id")
            if isinstance(raw_id, dict):
                for key_name in ("open_id", "user_id", "union_id"):
                    value = str(raw_id.get(key_name) or "").strip()
                    if value:
                        tokens.add(value)
            else:
                value = str(raw_id or "").strip()
                if value:
                    tokens.add(value)

    raw_content = message.get("content")
    if isinstance(raw_content, str):
        try:
            content_text = json.loads(raw_content).get("text", "")
        except Exception:
            content_text = raw_content
        for matched in _AT_MENTION_RE.findall(content_text):
            token = matched.strip()
            if token:
                tokens.add(token)
    return tokens


def _has_direct_mention(mention_tokens: set[str]) -> bool:
    lowered = {token.strip().lower() for token in mention_tokens if token.strip()}
    return any(token not in {"all", "_all", "@all", "@_all"} for token in lowered)


def resolve_feishu_ws_client_config(channel_config: dict) -> dict[str, str] | None:
    connection_mode = str(
        channel_config.get("connectionMode")
        or channel_config.get("mode")
        or "websocket"
    ).strip().lower()
    if connection_mode != "websocket":
        return None

    app_id = str(channel_config.get("appId") or channel_config.get("app_id") or "").strip()
    app_secret = str(channel_config.get("appSecret") or channel_config.get("app_secret") or "").strip()
    if not app_id or not app_secret:
        return None

    return {
        "app_id": app_id,
        "app_secret": app_secret,
        "encrypt_key": str(
            channel_config.get("encryptKey") or channel_config.get("encrypt_key") or ""
        ).strip(),
        "verification_token": str(
            channel_config.get("verificationToken")
            or channel_config.get("verification_token")
            or ""
        ).strip(),
    }


def _resolve_group_config(channel_config: dict, chat_id: str) -> tuple[dict, bool]:
    groups = channel_config.get("groups")
    if not isinstance(groups, dict):
        return {}, False

    merged: dict = {}
    wildcard_cfg = groups.get("*")
    if isinstance(wildcard_cfg, dict):
        merged.update(wildcard_cfg)

    explicit_cfg = groups.get(chat_id)
    explicit = isinstance(explicit_cfg, dict)
    if explicit:
        merged.update(explicit_cfg)
    return merged, explicit


def should_route_feishu_message(
    channel_config: dict,
    *,
    chat_type: str,
    chat_id: str,
    sender_open_id: str,
    mention_tokens: set[str],
) -> bool:
    if chat_type == "group":
        group_config, explicit_group = _resolve_group_config(channel_config, chat_id)
        if group_config.get("enabled") is False:
            return False

        group_policy = str(group_config.get("groupPolicy") or channel_config.get("groupPolicy") or "open")
        require_mention = bool(group_config.get("requireMention", channel_config.get("requireMention", False)))
        if group_policy == "mention":
            group_policy = "open"
            require_mention = True

        if group_policy == "disabled":
            return False

        group_allowlist = _coerce_allowlist(group_config.get("groupAllowFrom"))
        if not group_allowlist:
            group_allowlist = _coerce_allowlist(channel_config.get("groupAllowFrom"))
        if group_policy == "allowlist" and not explicit_group and not _allowlist_matches(group_allowlist, chat_id):
            return False

        sender_allowlist = _coerce_allowlist(group_config.get("allowFrom"))
        if not sender_allowlist:
            sender_allowlist = _coerce_allowlist(channel_config.get("groupSenderAllowFrom"))
        if sender_allowlist and not _allowlist_matches(sender_allowlist, sender_open_id):
            return False

        if require_mention and not _has_direct_mention(mention_tokens):
            return False
        return True

    dm_policy = str(channel_config.get("dmPolicy") or "open")
    if dm_policy == "disabled":
        return False

    allowlist = _coerce_allowlist(channel_config.get("allowFrom"))
    if dm_policy == "allowlist":
        return _allowlist_matches(allowlist, sender_open_id)
    if dm_policy == "open" and allowlist:
        return _allowlist_matches(allowlist, sender_open_id)
    return True


async def _handle_message_event(
    chat_id: str,
    sender_open_id: str,
    content: str,
    *,
    chat_type: str = "",
    mention_tokens: set[str] | None = None,
) -> None:
    """Core message routing — shared between webhook and ws modes.

    Matching priority:
    1. chat_id → HumanHex.channel_config.chat_id  (group chat)
    2. sender_open_id → user_oauth_connections → HumanHex.user_id  (private chat)
    """
    from sqlalchemy import select

    from app.core.deps import async_session_factory
    from app.models.base import not_deleted
    from app.models.corridor import HumanHex
    from app.services import workspace_message_service as msg_service

    if not content:
        return

    async with async_session_factory() as db:
        target_hex: HumanHex | None = None
        mention_tokens = mention_tokens or set()

        if chat_id:
            result = await db.execute(
                select(HumanHex).where(
                    HumanHex.channel_type == "feishu",
                    not_deleted(HumanHex),
                )
            )
            for hh in result.scalars().all():
                cfg = hh.channel_config or {}
                if cfg.get("chat_id") == chat_id:
                    if not should_route_feishu_message(
                        cfg,
                        chat_type=chat_type or "group",
                        chat_id=chat_id,
                        sender_open_id=sender_open_id,
                        mention_tokens=mention_tokens,
                    ):
                        logger.info(
                            "Feishu message skipped by policy: chat_id=%s open_id=%s",
                            chat_id,
                            sender_open_id,
                        )
                        return
                    target_hex = hh
                    break

        if not target_hex and sender_open_id and chat_type != "group":
            from app.models.oauth_connection import UserOAuthConnection
            oauth_q = await db.execute(
                select(UserOAuthConnection.user_id).where(
                    UserOAuthConnection.provider == "feishu",
                    UserOAuthConnection.provider_user_id == sender_open_id,
                    not_deleted(UserOAuthConnection),
                )
            )
            user_id = oauth_q.scalar_one_or_none()
            if user_id:
                hh_q = await db.execute(
                    select(HumanHex).where(
                        HumanHex.user_id == user_id,
                        not_deleted(HumanHex),
                    ).order_by(HumanHex.created_at.desc())
                )
                target_hex = hh_q.scalars().first()

        if not target_hex:
            logger.warning(
                "Feishu message: no human hex for chat_id=%s open_id=%s",
                chat_id, sender_open_id,
            )
            return

        workspace_id = target_hex.workspace_id

        await msg_service.record_message(
            db,
            workspace_id=workspace_id,
            sender_type="human",
            sender_id=target_hex.user_id,
            sender_name=f"Human:{target_hex.user_id}",
            content=content,
            message_type="chat",
        )

        from app.services import corridor_router

        endpoints, _hooks = await corridor_router.get_reachable_endpoints(
            workspace_id, target_hex.hex_q, target_hex.hex_r, db
        )
        agent_ids = [ep.entity_id for ep in endpoints if ep.endpoint_type == "agent"]
        if agent_ids:
            from app.services.collaboration_service import send_system_message_to_agents

            await send_system_message_to_agents(
                workspace_id, agent_ids, content, db
            )

        from app.api.workspaces import broadcast_event

        broadcast_event(workspace_id, "human:message_received", {
            "user_id": target_hex.user_id,
            "content": content[:200],
        })


def _extract_text_content(message: dict) -> str:
    msg_type = message.get("message_type", "")
    if msg_type == "text":
        try:
            return json.loads(message.get("content", "{}")).get("text", "")
        except Exception:
            return message.get("content", "")
    return f"[{msg_type} message]"


class FeishuWSClient:
    """Manages a single Feishu WebSocket long-connection for one app."""

    def __init__(self, app_id: str, app_secret: str, encrypt_key: str = "", verification_token: str = ""):
        self._app_id = app_id
        self._app_secret = app_secret
        self._thread: threading.Thread | None = None
        self._client: LarkWSClient | None = None

        handler = (
            EventDispatcherHandler.builder(encrypt_key, verification_token)
            .register_p2_im_message_receive_v1(self._on_message)
            .build()
        )

        self._client = LarkWSClient(
            app_id=app_id,
            app_secret=app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.WARNING,
        )

    def _on_message(self, event: P2ImMessageReceiveV1) -> None:
        """Called by lark-oapi when im.message.receive_v1 arrives."""
        import asyncio

        msg = event.event.message
        sender = event.event.sender

        chat_id = msg.chat_id if msg else ""
        chat_type = msg.chat_type if msg else ""
        sender_open_id = sender.sender_id.open_id if sender and sender.sender_id else ""

        message_dict = {}
        if msg:
            message_dict = {
                "message_type": msg.message_type or "",
                "content": msg.content or "",
                "mentions": [
                    {
                        "key": getattr(item, "key", None),
                        "id": {
                            "open_id": getattr(getattr(item, "id", None), "open_id", None),
                            "user_id": getattr(getattr(item, "id", None), "user_id", None),
                            "union_id": getattr(getattr(item, "id", None), "union_id", None),
                        },
                    }
                    for item in (getattr(msg, "mentions", None) or [])
                ],
            }
        content = _extract_text_content(message_dict)
        mention_tokens = _extract_mention_tokens(message_dict)

        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                _handle_message_event(
                    chat_id,
                    sender_open_id,
                    content,
                    chat_type=chat_type or "",
                    mention_tokens=mention_tokens,
                )
            )
            loop.close()
        except Exception as e:
            logger.error("Feishu WS message handling error: %s", e)

    def start(self) -> None:
        """Start the WebSocket connection in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Feishu WS client already running for app_id=%s", self._app_id)
            return

        def _run() -> None:
            try:
                logger.info("Starting Feishu WS long-connection: app_id=%s", self._app_id)
                self._client.start()
            except Exception as e:
                logger.error("Feishu WS client crashed: app_id=%s err=%s", self._app_id, e)

        self._thread = threading.Thread(target=_run, daemon=True, name=f"feishu-ws-{self._app_id[:8]}")
        self._thread.start()

    def stop(self) -> None:
        """Best-effort shutdown. The daemon thread will terminate with the process."""
        logger.info("Stopping Feishu WS client: app_id=%s", self._app_id)
