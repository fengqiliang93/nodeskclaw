"""RuntimeRegistry — maps runtime identifiers to RuntimeAdapter factories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeSpec:
    runtime_id: str
    description: str | None = None
    requires_companion: bool = False
    config_schema: dict | None = None


class RuntimeRegistry:
    def __init__(self) -> None:
        self._runtimes: dict[str, RuntimeSpec] = {}
        self._factories: dict[str, Any] = {}

    def register(self, spec: RuntimeSpec, factory: Any = None) -> None:
        self._runtimes[spec.runtime_id] = spec
        if factory is not None:
            self._factories[spec.runtime_id] = factory
        logger.debug("Registered runtime: %s", spec.runtime_id)

    def get(self, runtime_id: str) -> RuntimeSpec | None:
        return self._runtimes.get(runtime_id)

    def get_factory(self, runtime_id: str) -> Any | None:
        return self._factories.get(runtime_id)

    def all_runtimes(self) -> list[RuntimeSpec]:
        return list(self._runtimes.values())


RUNTIME_REGISTRY = RuntimeRegistry()

RUNTIME_REGISTRY.register(RuntimeSpec(
    runtime_id="openclaw",
    description="OpenClaw runtime — primary DeskClaw agent kernel.",
    requires_companion=False,
))

RUNTIME_REGISTRY.register(RuntimeSpec(
    runtime_id="claude_code",
    description="Claude Code runtime — CLI-based agent via Companion sidecar.",
    requires_companion=True,
))

RUNTIME_REGISTRY.register(RuntimeSpec(
    runtime_id="generic_http",
    description="Generic HTTP runtime — OpenAI-compatible API endpoint.",
    requires_companion=False,
))
