"""ComputeRegistry — maps compute provider identifiers to ComputeProvider instances."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComputeSpec:
    compute_id: str
    provider: Any = None
    description: str | None = None
    supports_sidecar: bool = True
    config_schema: dict | None = None


class ComputeRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ComputeSpec] = {}

    def register(self, spec: ComputeSpec) -> None:
        self._providers[spec.compute_id] = spec
        logger.debug("Registered compute provider: %s", spec.compute_id)

    def get(self, compute_id: str) -> ComputeSpec | None:
        return self._providers.get(compute_id)

    def all_providers(self) -> list[ComputeSpec]:
        return list(self._providers.values())


COMPUTE_REGISTRY = ComputeRegistry()


def _register_builtins() -> None:
    from app.services.runtime.compute.docker_provider import DockerComputeProvider
    from app.services.runtime.compute.k8s_provider import K8sComputeProvider
    from app.services.runtime.compute.process_provider import ProcessComputeProvider

    COMPUTE_REGISTRY.register(ComputeSpec(
        compute_id="k8s",
        provider=K8sComputeProvider(),
        description="Kubernetes compute -- Deployment + Service + NetworkPolicy.",
        supports_sidecar=True,
    ))
    COMPUTE_REGISTRY.register(ComputeSpec(
        compute_id="docker",
        provider=DockerComputeProvider(),
        description="Docker compose compute -- local container orchestration.",
        supports_sidecar=True,
    ))
    COMPUTE_REGISTRY.register(ComputeSpec(
        compute_id="process",
        provider=ProcessComputeProvider(),
        description="Local process compute -- subprocess management for dev/testing.",
        supports_sidecar=False,
    ))


_register_builtins()
