"""AgentRuntimeAdapter — protocol defining how the platform communicates with agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class RuntimeSession:
    session_id: str
    runtime_id: str
    instance_id: str
    workspace_id: str
    base_url: str
    token: str
    extra: dict = field(default_factory=dict)


@dataclass
class ResponseChunk:
    content: str = ""
    is_done: bool = False
    is_error: bool = False
    error_message: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class RuntimeCapabilities:
    runtime_id: str
    supports_streaming: bool = True
    supports_tool_use: bool = False
    supports_multi_turn: bool = True
    supports_system_prompt: bool = True
    max_context_tokens: int = 128000
    extra: dict = field(default_factory=dict)


class AgentRuntimeAdapter(Protocol):
    async def create_session(
        self,
        instance_id: str,
        workspace_id: str,
        *,
        base_url: str,
        token: str,
        extra: dict | None = None,
    ) -> RuntimeSession: ...

    async def send_message(
        self,
        session: RuntimeSession,
        messages: list[dict],
        *,
        stream: bool = True,
    ) -> AsyncIterator[ResponseChunk]: ...

    async def health_check(self, session: RuntimeSession) -> bool: ...

    async def get_capabilities(self, session: RuntimeSession) -> RuntimeCapabilities: ...

    async def destroy_session(self, session: RuntimeSession) -> None: ...
