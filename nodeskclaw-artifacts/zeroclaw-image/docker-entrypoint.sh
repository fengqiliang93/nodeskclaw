#!/bin/bash
set -euo pipefail

if [ -f /opt/zeroclaw/.zeroclaw-version ]; then
  echo "ZeroClaw image version: $(cat /opt/zeroclaw/.zeroclaw-version)"
fi

if [ -n "${NODESKCLAW_API_URL:-}" ] && [ -n "${NODESKCLAW_INSTANCE_ID:-}" ]; then
  echo "Starting NoDeskClaw tunnel bridge..."
  python3 -m nodeskclaw_tunnel_bridge --runtime zeroclaw &
fi

exec "$@"
