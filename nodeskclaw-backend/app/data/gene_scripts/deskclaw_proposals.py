#!/usr/bin/env python3
"""DeskClaw Proposals Tool -- submit approval requests and check trust policies.

Usage:
  python3 deskclaw_proposals.py <action> [options]

Actions:
  check_trust --instance-id ID --action-type TYPE     Check if an action is already trusted
  submit_request --instance-id ID --action-type TYPE --proposal JSON [--context TEXT]
                                                      Submit an approval request
  list_decisions [--agent-id ID] [--type TYPE]         List past decision records
  get_decision --record-id ID                          Get decision record details

Environment:
  DESKCLAW_API_URL        Backend API base URL
  DESKCLAW_TOKEN          Instance proxy_token
  DESKCLAW_WORKSPACE_ID   Workspace ID
  DESKCLAW_INSTANCE_ID    Current instance ID (for default --instance-id)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from _api_client import api_call, _output, _fatal, WORKSPACE_ID


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deskclaw_proposals", description="DeskClaw Proposals Tool")
    sub = p.add_subparsers(dest="action", required=True)

    default_iid = os.environ.get("DESKCLAW_INSTANCE_ID", "")

    sp = sub.add_parser("check_trust", help="Check if an action is already trusted")
    sp.add_argument("--instance-id", default=default_iid)
    sp.add_argument("--action-type", required=True)

    sp = sub.add_parser("submit_request", help="Submit an approval request")
    sp.add_argument("--instance-id", default=default_iid)
    sp.add_argument("--action-type", required=True)
    sp.add_argument("--proposal", required=True, help="JSON object with proposal data")
    sp.add_argument("--context", help="Context summary explaining the request")

    sp = sub.add_parser("list_decisions", help="List past decision records")
    sp.add_argument("--agent-id")
    sp.add_argument("--type", dest="decision_type")

    sp = sub.add_parser("get_decision", help="Get decision record details")
    sp.add_argument("--record-id", required=True)

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    action = args.action

    if action == "check_trust":
        if not args.instance_id:
            _fatal("--instance-id is required (or set DESKCLAW_INSTANCE_ID)")
        qs = f"?workspace_id={WORKSPACE_ID}&agent_instance_id={args.instance_id}&action_type={args.action_type}"
        _output(api_call("GET", f"/workspaces/trust-policies/check{qs}", ws=False))

    elif action == "submit_request":
        if not args.instance_id:
            _fatal("--instance-id is required (or set DESKCLAW_INSTANCE_ID)")
        try:
            proposal_data = json.loads(args.proposal)
        except json.JSONDecodeError:
            _fatal("--proposal must be valid JSON")
            return
        body = {
            "workspace_id": WORKSPACE_ID,
            "agent_instance_id": args.instance_id,
            "action_type": args.action_type,
            "proposal": proposal_data,
        }
        if args.context:
            body["context_summary"] = args.context
        _output(api_call("POST", "/workspaces/approval-requests", body, ws=False))

    elif action == "list_decisions":
        params = []
        if args.agent_id:
            params.append(f"agent_id={args.agent_id}")
        if args.decision_type:
            params.append(f"decision_type={args.decision_type}")
        qs = f"?{'&'.join(params)}" if params else ""
        _output(api_call("GET", f"/workspaces/{WORKSPACE_ID}/decision-records{qs}", ws=False))

    elif action == "get_decision":
        _output(api_call("GET", f"/workspaces/{WORKSPACE_ID}/decision-records/{args.record_id}", ws=False))


if __name__ == "__main__":
    main()
