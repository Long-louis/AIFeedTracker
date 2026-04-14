#!/usr/bin/env python3
"""Minimal smoke test for the ASR health endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_BASE_URL = os.getenv("ASR_BASE_URL", "http://127.0.0.1:8900")


def fetch_health(base_url: str, timeout: float) -> dict[str, object]:
    url = f"{base_url.rstrip('/')}/health"
    request = urllib.request.Request(url=url, method="GET")

    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise AssertionError(f"Expected HTTP 200, got {response.status}")

        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict):
        raise AssertionError("Expected JSON object payload")

    status = payload.get("status")
    if status not in {"ok", "degraded"}:
        raise AssertionError("Expected status to be 'ok' or 'degraded'")

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test ASR /health endpoint")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    try:
        payload = fetch_health(args.base_url, args.timeout)
    except (urllib.error.URLError, json.JSONDecodeError, AssertionError) as exc:
        print(f"STATUS: FAIL - {exc}")
        return 1

    print(f"STATUS: PASS - /health status={payload['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
