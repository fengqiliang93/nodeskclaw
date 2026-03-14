"""Tunnel module — unified WebSocket tunnel for backend <-> instance communication."""

from app.services.tunnel.adapter import TunnelAdapter

tunnel_adapter = TunnelAdapter()

__all__ = ["tunnel_adapter", "TunnelAdapter"]
