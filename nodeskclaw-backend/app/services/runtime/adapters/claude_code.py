"""ClaudeCodeAdapter — communicates with Claude Code agents via Companion HTTP sidecar."""

from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

import httpx

from app.services.runtime.adapters.base import (
    ResponseChunk,
    RuntimeCapabilities,
    RuntimeSession,
)

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter:
    """Adapter for Claude Code runtime — CLI-based agent via Companion sidecar."""

    runtime_id = "claude_code"

    async def create_session(
        self,
        instance_id: str,
        workspace_id: str,
        *,
        base_url: str,
        token: str,
        extra: dict | None = None,
    ) -> RuntimeSession:
        return RuntimeSession(
            session_id=str(uuid.uuid4()),
            runtime_id=self.runtime_id,
            instance_id=instance_id,
            workspace_id=workspace_id,
            base_url=base_url,
            token=token,
            extra=extra or {},
        )

    async def send_message(
        self,
        session: RuntimeSession,
        messages: list[dict],
        *,
        stream: bool = True,
    ) -> AsyncIterator[ResponseChunk]:
        url = f"{session.base_url}/send"
        headers = {"Content-Type": "application/json"}
        if session.token:
            headers["Authorization"] = f"Bearer {session.token}"

        try:
            async with httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0"),
                timeout=300,
            ) as client:
                resp = await client.post(url, headers=headers, json={
                    "messages": messages,
                    "session_id": session.session_id,
                    "workspace_id": session.workspace_id,
                })
                if resp.status_code != 200:
                    yield ResponseChunk(is_error=True, error_message=f"Companion HTTP {resp.status_code}")
                    return
                data = resp.json()
                content = data.get("response", "")
                yield ResponseChunk(content=content, is_done=True, raw=data)
        except Exception as e:
            logger.error("ClaudeCode send_message failed: %s", e)
            yield ResponseChunk(is_error=True, error_message=str(e))

    async def health_check(self, session: RuntimeSession) -> bool:
        url = f"{session.base_url}/health"
        try:
            async with httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0"),
                timeout=10,
            ) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    async def get_capabilities(self, session: RuntimeSession) -> RuntimeCapabilities:
        url = f"{session.base_url}/capabilities"
        try:
            async with httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0"),
                timeout=10,
            ) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return RuntimeCapabilities(
                        runtime_id=self.runtime_id,
                        supports_streaming=data.get("supports_streaming", False),
                        supports_tool_use=data.get("supports_tool_use", True),
                        supports_multi_turn=data.get("supports_multi_turn", True),
                        supports_system_prompt=data.get("supports_system_prompt", True),
                        extra=data,
                    )
        except Exception:
            pass
        return RuntimeCapabilities(runtime_id=self.runtime_id)

    async def destroy_session(self, session: RuntimeSession) -> None:
        url = f"{session.base_url}/cancel"
        try:
            async with httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0"),
                timeout=10,
            ) as client:
                await client.post(url, json={"session_id": session.session_id})
        except Exception:
            pass
