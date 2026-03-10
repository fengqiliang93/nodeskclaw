"""DeliveryPlan — describes how a message should be delivered to its targets."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeliveryTarget:
    node_id: str
    node_type: str = ""
    transport: str = ""
    priority_override: str | None = None


@dataclass
class DeliveryPlan:
    targets: list[str] = field(default_factory=list)
    resolved_targets: list[DeliveryTarget] = field(default_factory=list)
    mode: str = "multicast"
    workspace_id: str = ""
    topology_version: int = 0
    paths: list[list[str]] = field(default_factory=list)
    ignore_topology: bool = False
    needs_topology_resolution: bool = False
