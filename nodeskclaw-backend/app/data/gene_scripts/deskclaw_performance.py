#!/usr/bin/env python3
"""DeskClaw Performance Tool -- read agent performance metrics.

Usage:
  python3 deskclaw_performance.py <action> [options]

Actions:
  get_my_performance [--instance-id ID]   Your own performance metrics
  get_team_performance                    All team members' metrics
  collect_performance                     Trigger fresh data collection
  attribute_tokens                        Attribute token costs to tasks

Environment:
  DESKCLAW_API_URL        Backend API base URL
  DESKCLAW_TOKEN          Instance proxy_token
  DESKCLAW_WORKSPACE_ID   Workspace ID
  DESKCLAW_INSTANCE_ID    Current instance ID (for get_my_performance default)
"""

from __future__ import annotations

import argparse
import os

from _api_client import api_call, _output


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deskclaw_performance", description="DeskClaw Performance Tool")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("get_my_performance", help="Your own performance metrics")
    sp.add_argument("--instance-id", default=os.environ.get("DESKCLAW_INSTANCE_ID", ""),
                     help="Instance ID (defaults to DESKCLAW_INSTANCE_ID)")

    sub.add_parser("get_team_performance", help="All team members' metrics")

    sub.add_parser("collect_performance", help="Trigger fresh data collection")

    sub.add_parser("attribute_tokens", help="Attribute token costs to tasks")

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    action = args.action
    base = "/performance"

    if action == "get_my_performance":
        iid = args.instance_id
        qs = f"?instance_id={iid}" if iid else ""
        _output(api_call("GET", f"{base}{qs}"))

    elif action == "get_team_performance":
        _output(api_call("GET", base))

    elif action == "collect_performance":
        _output(api_call("POST", f"{base}/collect"))

    elif action == "attribute_tokens":
        _output(api_call("POST", f"{base}/attribute-tokens"))


if __name__ == "__main__":
    main()
