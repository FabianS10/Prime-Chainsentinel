#!/usr/bin/env python3
"""Check browser CORS and authentication behavior on a live Render backend.

Usage:
  python scripts/check_cors.py https://YOUR-API.onrender.com https://YOUR-SITE.netlify.app

Read-only; uses only Python's standard library. Never sends credentials.
"""
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse


def origin(value):
    value = value.rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise ValueError("Provide an HTTPS origin only (scheme + host; no path)")
    return value


def fetch(base, path, method, headers):
    req = urllib.request.Request(base + path, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, response.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers


def check_preflight(api, frontend, path, intended_method):
    code, headers = fetch(
        api,
        path,
        "OPTIONS",
        {
            "Origin": frontend,
            "Access-Control-Request-Method": intended_method,
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    allowed_origin = headers.get("Access-Control-Allow-Origin")
    allowed_headers = (headers.get("Access-Control-Allow-Headers") or "").lower()
    allowed_methods = (headers.get("Access-Control-Allow-Methods") or "").upper()
    valid = (
        code == 200
        and allowed_origin == frontend
        and intended_method in allowed_methods
        and "authorization" in allowed_headers
        and "content-type" in allowed_headers
    )
    print(f"{'PASS' if valid else 'FAIL'} OPTIONS {path}: HTTP {code}")
    print(f"  allow-origin: {allowed_origin!r}")
    print(f"  allow-methods: {allowed_methods!r}")
    print(f"  allow-headers: {allowed_headers!r}")
    return valid


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/check_cors.py https://API.onrender.com https://SITE.netlify.app")
        return 2
    api, frontend = map(origin, sys.argv[1:])
    checks = [
        check_preflight(api, frontend, "/api/baselines/summary", "GET"),
        check_preflight(api, frontend, "/api/imports", "POST"),
        check_preflight(api, frontend, "/api/reports/generate", "POST"),
    ]
    code, headers = fetch(api, "/api/baselines/summary", "GET", {"Origin": frontend})
    allowed = headers.get("Access-Control-Allow-Origin")
    ok = code == 401 and allowed == frontend
    print(f"{'PASS' if ok else 'FAIL'} unauthenticated GET /api/baselines/summary: HTTP {code}; allow-origin={allowed!r}")
    if code == 200:
        print("WARNING: the API may be publicly readable without demo authentication.")
    checks.append(ok)

    # Confirm that the API does not allow a non-configured site.
    wrong = "https://not-the-thesis-frontend.invalid"
    code, headers = fetch(
        api, "/api/baselines/summary", "OPTIONS",
        {"Origin": wrong, "Access-Control-Request-Method": "GET"},
    )
    blocked = headers.get("Access-Control-Allow-Origin") != wrong
    print(f"{'PASS' if blocked else 'FAIL'} unapproved origin rejected: HTTP {code}")
    checks.append(blocked)
    if all(checks):
        print("All CORS/anonymous-auth checks passed. Verify login, uploads, calculations and PDF in Netlify next.")
        return 0
    print("One or more checks failed. Compare Render's CORS_ORIGINS to the actual Netlify URL, then redeploy Render.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"CORS check could not complete: {exc}", file=sys.stderr)
        sys.exit(2)
