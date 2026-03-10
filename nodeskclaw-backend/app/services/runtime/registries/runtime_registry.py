"""RuntimeRegistry — maps runtime identifiers to RuntimeAdapter factories."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeSpec:
    runtime_id: str
    adapter: Any = None
    description: str | None = None
    requires_companion: bool = False
    config_schema: dict | None = None


class RuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, RuntimeSpec] = {}

    def register(self, spec: RuntimeSpec) -> None:
        self._runtimes[spec.runtime_id] = spec
        logger.debug("Registered runtime: %s", spec.runtime_id)

    def get(self, runtime_id: str) -> RuntimeSpec | None:
        return self._runtimes.get(runtime_id)

    def all_runtimes(self) -> list[RuntimeSpec]:
        return list(self._runtimes.values())


RUNTIME_REGISTRY = RuntimeRegistry()


def _register_builtins() -> None:
    from app.services.runtime.adapters.claude_code import ClaudeCodeAdapter
    from app.services.runtime.adapters.generic_http import GenericHTTPAdapter
    from app.services.runtime.adapters.openclaw import OpenClawRuntimeAdapter

    RUNTIME_REGISTRY.register(RuntimeSpec(
        runtime_id="openclaw",
        adapter=OpenClawRuntimeAdapter(),
        description="OpenClaw runtime -- primary DeskClaw agent kernel.",
        requires_companion=False,
    ))
    RUNTIME_REGISTRY.register(RuntimeSpec(
        runtime_id="claude_code",
        adapter=ClaudeCodeAdapter(),
        description="Claude Code runtime -- CLI-based agent via Companion sidecar.",
        requires_companion=True,
    ))
    RUNTIME_REGISTRY.register(RuntimeSpec(
        runtime_id="generic_http",
        adapter=GenericHTTPAdapter(),
        description="Generic HTTP runtime -- OpenAI-compatible API endpoint.",
        requires_companion=False,
    ))


_register_builtins()
