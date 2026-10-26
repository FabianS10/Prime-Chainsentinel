#!/usr/bin/env python3
"""Read-only checks for the Prime ChainSentinel live thesis demo.

Run: python scripts/defense_smoke_test.py
Optional: python scripts/defense_smoke_test.py --market
Credentials are read from root .env and are not printed in logs.
"""
import argparse
import base64
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def credentials():
    variables = {}
    file_path = ROOT / ".env"
    if not file_path.exists():
        raise RuntimeError("Create a root .env from .env.defense.example first.")
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        variables[key.strip()] = value.strip().strip("'").strip('"')
    username = variables.get("PCS_DEMO_USERNAME", "")
    password = variables.get("PCS_DEMO_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("Both PCS_DEMO_USERNAME and PCS_DEMO_PASSWORD must be set in .env.")
    return username, password


def check(base, path, auth, expect_json=True, timeout=30):
    request = urllib.request.Request(base + path, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            if expect_json:
                result = json.loads(body)
                print(f"PASS {path} ({response.status})")
                return result
            if b"<html" not in body.lower():
                raise RuntimeError("Frontend is not HTML")
            print(f"PASS {path} (frontend served)")
    except (urllib.error.URLError, ValueError) as exc:
        raise RuntimeError(f"FAIL {path}: {exc}") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000", help="Base URL, with no trailing slash")
    parser.add_argument("--market", action="store_true", help="Also test a real Yahoo Finance query")
    parser.add_argument("--backend-only", action="store_true", help="Expect FastAPI JSON at / instead of a locally served React build")
    args = parser.parse_args()
    username, password = credentials()
    auth = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
    base = args.base.rstrip("/")
    health = check(base, "/health", auth)
    if health.get("status") != "ok":
        raise RuntimeError(f"Health status not ok: {health!r}")
    root = check(base, "/", auth, expect_json=args.backend_only)
    if args.backend_only and root.get("app") != "Prime ChainSentinel":
        raise RuntimeError("The root did not return the expected API identity")
    check(base, "/api/imports", auth)
    summary = check(base, "/api/baselines/summary", auth)
    check(base, "/api/provenance/summary", auth)
    if not summary.get("available", False):
        print("WARNING: no active imported MI300X evidence; import sample_data/MI300X_Benchmarks.zip before defense.")
    if args.market:
        check(base, "/api/market/metrics/VTI?years=1", auth, timeout=120)
        print("Market endpoint reached; inspect observed-data provenance labels in browser.")
    print("Read-only smoke tests completed. Financial simulations and PDF export still need browser verification.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
