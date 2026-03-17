#!/usr/bin/env python3
"""DeskClaw Topology Tool -- query workspace topology and neighbor information.

Usage:
  python3 deskclaw_topology.py <action> [options]

Actions:
  get_topology                         Full workspace topology (nodes and edges)
  get_reachable --instance-id ID       Nodes reachable from a specific instance
  get_health                           Topology health summary
  get_message_flow                     Message flow statistics

Environment:
  DESKCLAW_API_URL        Backend API base URL
  DESKCLAW_TOKEN          Instance proxy_token
  DESKCLAW_WORKSPACE_ID   Workspace ID
  DESKCLAW_INSTANCE_ID    Current instance ID (for get_reachable default)
"""

from __future__ import annotations

import argparse
import os

from _api_client import api_call, _output


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deskclaw_topology", description="DeskClaw Topology Tool")
    sub = p.add_subparsers(dest="action", required=True)

    sub.add_parser("get_topology", help="Full workspace topology")

    sp = sub.add_parser("get_reachable", help="Nodes reachable from an instance")
    sp.add_argument("--instance-id", default=os.environ.get("DESKCLAW_INSTANCE_ID", ""),
                     help="Instance ID (defaults to DESKCLAW_INSTANCE_ID env var)")

    sub.add_parser("get_health", help="Topology health summary")

    sub.add_parser("get_message_flow", help="Message flow statistics")

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    action = args.action
    base = "/topology"

    if action == "get_topology":
        _output(api_call("GET", base))

    elif action == "get_reachable":
        iid = args.instance_id
        if not iid:
            from _api_client import _fatal
            _fatal("--instance-id is required (or set DESKCLAW_INSTANCE_ID)")
        _output(api_call("GET", f"{base}/reachable?instance_id={iid}"))

    elif action == "get_health":
        _output(api_call("GET", f"{base}/health"))

    elif action == "get_message_flow":
        _output(api_call("GET", f"{base}/message-flow"))


if __name__ == "__main__":
    main()
