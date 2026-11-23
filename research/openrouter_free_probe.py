#!/usr/bin/env python3
"""Run exactly one free-only OpenRouter call. NO Metaculus posting or recurring loop.

Usage: OPENROUTER_API_KEY=... python research/openrouter_free_probe.py
Never print the key or put it into a tracked file.
"""
import json
import os
import sys
import urllib.error
import urllib.request

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"   # Explicit free-only router. NOT openrouter/auto.
MAX_TOKENS = 32

def build_payload():
    return {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Answer only with the word OK."}],
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }

def run():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print("Missing OPENROUTER_API_KEY environment variable", file=sys.stderr)
        return 2
    request = urllib.request.Request(
        URL,
        data=json.dumps(build_payload()).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/pencil-source/metac-bot-template",
            "X-Title": "PencilForecast Free Probe",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        # Error body may contain sensitive details; do not print it.
        print(f"Free-only request blocked (HTTP {exc.code}). No fallback attempted.")
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Free-only request failed: {type(exc).__name__}. No fallback attempted.")
        return 1
    print("Free-only API request completed.")
    print("Served model:", data.get("model", "not reported"))
    usage = data.get("usage") or {}
    # Many providers do not supply cost. Never imply $0 billed from a missing field.
    cost = usage.get("cost")
    print("Provider-reported cost (USD):", cost if cost is not None else "not reported")
    print("No predictions were submitted to Metaculus.")
    return 0

if __name__ == "__main__":
    raise SystemExit(run())
