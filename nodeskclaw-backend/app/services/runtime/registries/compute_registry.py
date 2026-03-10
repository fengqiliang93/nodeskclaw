"""ComputeRegistry — maps compute provider identifiers to ComputeProvider factories."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComputeSpec:
    compute_id: str
    description: str | None = None
    supports_sidecar: bool = True
    config_schema: dict | None = None


class ComputeRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ComputeSpec] = {}
        self._factories: dict[str, Any] = {}

    def register(self, spec: ComputeSpec, factory: Any = None) -> None:
        self._providers[spec.compute_id] = spec
        if factory is not None:
            self._factories[spec.compute_id] = factory
        logger.debug("Registered compute provider: %s", spec.compute_id)

    def get(self, compute_id: str) -> ComputeSpec | None:
        return self._providers.get(compute_id)

    def get_factory(self, compute_id: str) -> Any | None:
        return self._factories.get(compute_id)

    def all_providers(self) -> list[ComputeSpec]:
        return list(self._providers.values())


COMPUTE_REGISTRY = ComputeRegistry()

COMPUTE_REGISTRY.register(ComputeSpec(
    compute_id="k8s",
    description="Kubernetes compute — Deployment + Service + NetworkPolicy.",
    supports_sidecar=True,
))

COMPUTE_REGISTRY.register(ComputeSpec(
    compute_id="docker",
    description="Docker compose compute — local container orchestration.",
    supports_sidecar=True,
))
