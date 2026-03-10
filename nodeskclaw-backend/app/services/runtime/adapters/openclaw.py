"""OpenClawRuntimeAdapter — communicates with OpenClaw instances via their chat completions API."""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

import httpx

from app.services.runtime.adapters.base import (
    AgentRuntimeAdapter,
    ResponseChunk,
    RuntimeCapabilities,
    RuntimeSession,
)

logger = logging.getLogger(__name__)


class OpenClawRuntimeAdapter:
    """Adapter for OpenClaw runtime — the primary DeskClaw agent kernel."""

    runtime_id = "openclaw"

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
        url = f"{session.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {session.token}",
            "Content-Type": "application/json",
            "X-OpenClaw-Session-Key": f"workspace:{session.workspace_id}",
        }
        payload = {"model": "gpt-4", "messages": messages, "stream": stream}

        async with httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0"),
            timeout=120,
        ) as client:
            if not stream:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    yield ResponseChunk(is_error=True, error_message=f"HTTP {resp.status_code}")
                    return
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                yield ResponseChunk(content=content, is_done=True, raw=data)
                return

            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    yield ResponseChunk(
                        is_error=True,
                        error_message=f"HTTP {resp.status_code}",
                    )
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk_data = line[6:]
                    if chunk_data == "[DONE]":
                        yield ResponseChunk(is_done=True)
                        return
                    try:
                        chunk = json.loads(chunk_data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield ResponseChunk(content=content, raw=chunk)
                    except json.JSONDecodeError:
                        continue

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
        return RuntimeCapabilities(
            runtime_id=self.runtime_id,
            supports_streaming=True,
            supports_tool_use=True,
            supports_multi_turn=True,
            supports_system_prompt=True,
        )

    async def destroy_session(self, session: RuntimeSession) -> None:
        pass
