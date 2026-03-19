"""DingTalk channel adapter — delivers workspace messages to DingTalk via Bot API.

Supports group chat (openConversationId) and single chat (staffId) delivery.
Uses DingTalk new API (api.dingtalk.com) with OAuth2 access token.
"""

from __future__ import annotations

import json
import logging
import time

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.channel_adapters.base import ChannelAdapter

logger = logging.getLogger(__name__)

DINGTALK_API_BASE = "https://api.dingtalk.com"

_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_TOKEN_TTL = 7000


async def _get_access_token(app_key: str, app_secret: str) -> str:
    cache_key = app_key
    cached = _TOKEN_CACHE.get(cache_key)
    if cached and cached[1] > time.time():
        return cached[0]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{DINGTALK_API_BASE}/v1.0/oauth2/accessToken",
            json={"appKey": app_key, "appSecret": app_secret},
        )
        if resp.status_code != 200:
            logger.error("DingTalk accessToken request failed: %d %s", resp.status_code, resp.text[:300])
            return ""
        data = resp.json()
        token = data.get("accessToken", "")
        if token:
            _TOKEN_CACHE[cache_key] = (token, time.time() + _TOKEN_TTL)
        return token


async def get_dingtalk_staff_id(user_id: str, db: AsyncSession) -> str | None:
    from app.models.base import not_deleted
    from app.models.oauth_connection import UserOAuthConnection

    result = await db.execute(
        select(UserOAuthConnection.provider_user_id).where(
            UserOAuthConnection.user_id == user_id,
            UserOAuthConnection.provider == "dingtalk",
            not_deleted(UserOAuthConnection),
        ).order_by(UserOAuthConnection.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


class DingTalkChannelAdapter(ChannelAdapter):
    """Sends messages to DingTalk via Robot API."""

    def __init__(self, app_key: str, app_secret: str):
        self._app_key = app_key
        self._app_secret = app_secret

    async def _get_token(self) -> str:
        return await _get_access_token(self._app_key, self._app_secret)

    async def _send_to_conversation(
        self,
        *,
        token: str,
        open_conversation_id: str,
        robot_code: str,
        msg_key: str,
        msg_param: str,
    ) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{DINGTALK_API_BASE}/v1.0/robot/groupMessages/send",
                    headers={"x-acs-dingtalk-access-token": token},
                    json={
                        "robotCode": robot_code,
                        "openConversationId": open_conversation_id,
                        "msgKey": msg_key,
                        "msgParam": msg_param,
                    },
                )
                if resp.status_code == 200:
                    return True
                logger.warning("DingTalk group send failed: %d %s", resp.status_code, resp.text[:300])
                return False
        except Exception as e:
            logger.error("DingTalk group send error: %s", e)
            return False

    async def _send_to_user(
        self,
        *,
        token: str,
        staff_ids: list[str],
        robot_code: str,
        msg_key: str,
        msg_param: str,
    ) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{DINGTALK_API_BASE}/v1.0/robot/oToMessages/batchSend",
                    headers={"x-acs-dingtalk-access-token": token},
                    json={
                        "robotCode": robot_code,
                        "userIds": staff_ids,
                        "msgKey": msg_key,
                        "msgParam": msg_param,
                    },
                )
                if resp.status_code == 200:
                    return True
                logger.warning("DingTalk user send failed: %d %s", resp.status_code, resp.text[:300])
                return False
        except Exception as e:
            logger.error("DingTalk user send error: %s", e)
            return False

    async def send_message(
        self,
        *,
        channel_config: dict,
        sender_name: str,
        content: str,
        workspace_name: str,
        metadata: dict | None = None,
    ) -> bool:
        token = await self._get_token()
        if not token:
            logger.error("Failed to obtain DingTalk access token")
            return False

        robot_code = channel_config.get("robot_code") or self._app_key
        msg_key = "sampleMarkdown"
        text = f"[{workspace_name}] {sender_name}:\n\n{content}"
        msg_param = json.dumps({
            "title": f"[{workspace_name}] {sender_name}",
            "text": text,
        })

        open_conversation_id = channel_config.get("open_conversation_id", "")
        if open_conversation_id:
            return await self._send_to_conversation(
                token=token,
                open_conversation_id=open_conversation_id,
                robot_code=robot_code,
                msg_key=msg_key,
                msg_param=msg_param,
            )

        staff_id = channel_config.get("staff_id", "")
        if staff_id:
            return await self._send_to_user(
                token=token,
                staff_ids=[staff_id],
                robot_code=robot_code,
                msg_key=msg_key,
                msg_param=msg_param,
            )

        logger.warning("DingTalk channel_config missing both open_conversation_id and staff_id")
        return False

    async def send_approval_request(
        self,
        *,
        channel_config: dict,
        agent_name: str,
        action_type: str,
        proposal: dict,
        workspace_name: str,
        callback_url: str,
    ) -> bool:
        token = await self._get_token()
        if not token:
            return False

        robot_code = channel_config.get("robot_code") or self._app_key
        details = json.dumps(proposal, ensure_ascii=False, indent=2)[:500]
        msg_key = "sampleActionCard"
        msg_param = json.dumps({
            "title": f"[{workspace_name}] Approval Request",
            "text": (
                f"**AI Employee**: {agent_name}\n\n"
                f"**Action**: {action_type}\n\n"
                f"**Details**: {details}"
            ),
            "actionTitle1": "Allow",
            "actionURL1": f"{callback_url}?action=allow_once",
            "actionTitle2": "Deny",
            "actionURL2": f"{callback_url}?action=deny",
        })

        open_conversation_id = channel_config.get("open_conversation_id", "")
        if open_conversation_id:
            return await self._send_to_conversation(
                token=token,
                open_conversation_id=open_conversation_id,
                robot_code=robot_code,
                msg_key=msg_key,
                msg_param=msg_param,
            )

        staff_id = channel_config.get("staff_id", "")
        if staff_id:
            return await self._send_to_user(
                token=token,
                staff_ids=[staff_id],
                robot_code=robot_code,
                msg_key=msg_key,
                msg_param=msg_param,
            )

        return False
