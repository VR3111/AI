#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.request
import urllib.error
import socket
import os
from typing import Any

DEFAULT_API_URL = "http://127.0.0.1:8001/query"
DEFAULT_TIMEOUT = 30


def fail(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def post_json(url: str, payload: dict[str, Any], timeout: int):
    data = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    auth_token = os.getenv("P1_AUTH_TOKEN")
    if not auth_token:
        fail("P1_AUTH_TOKEN is not set", code=1)

    headers["Authorization"] = f"Bearer {auth_token}"

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return e.code, body
    except (urllib.error.URLError, socket.timeout) as e:
        fail(f"Transport error: {e}", code=1)


def main():
    parser = argparse.ArgumentParser(prog="p1", description="P1 thin CLI (raw JSON passthrough)")
    sub = parser.add_subparsers(dest="command", required=True)

    q = sub.add_parser("query", help="Send a query to P1")
    q.add_argument("--tenant-id", required=True)
    q.add_argument("--conversation-id", required=True)
    q.add_argument("--query", help="Question text")
    q.add_argument("--reset", action="store_true", help='Reset context (maps to query="new topic")')
    q.add_argument("--debug", action="store_true")
    q.add_argument("--api-url", default=DEFAULT_API_URL)
    q.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)

    args = parser.parse_args()

    if args.command == "query":
        if not args.query and not args.reset:
            fail("Either --query or --reset must be provided", code=1)

        query_text = "new topic" if args.reset else args.query

        payload = {
            "query": query_text,
            "conversation_id": args.conversation_id,
            "tenant_id": args.tenant_id,
            "debug": bool(args.debug),
        }

        status, body = post_json(args.api_url, payload, args.timeout)

        # Non-200 = API error (not refusal)
        if status < 200 or status >= 300:
            print(body)
            sys.exit(2)

        # Print raw JSON only
        print(body)
        sys.exit(0)


if __name__ == "__main__":
    main()
