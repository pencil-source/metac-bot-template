#!/usr/bin/env python3
"""One free-only forecast, for research; NO Metaculus posting or web search."""
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "nvidia/nemotron-3.5-super-vl:free"  # Pinned free model; fail closed if unavailable.
MAX_TOKENS = 650

def validate_question(question):
    question = question.strip()
    if not 12 <= len(question) <= 500:
        raise ValueError("Question must be 12 to 500 characters.")
    if "\n" in question or "\r" in question:
        raise ValueError("Question must fit on one line.")
    return question

def parse_forecast(text):
    """Parse strict JSON or a fenced JSON object without guessing probabilities."""
    if not isinstance(text, str):
        raise ValueError("Model did not return text.")
    cleaned = text.strip()
    fence = chr(96) * 3
    if cleaned.startswith(fence):
        cleaned = re.sub("^" + re.escape(fence) + r"(?:json)?\s*", "", cleaned, count=1, flags=re.I)
        cleaned = re.sub(r"\s*" + re.escape(fence) + "$", "", cleaned)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response was not valid JSON; no forecast recorded.") from exc
    if not isinstance(obj, dict) or set(obj) != {"probability", "reason"}:
        raise ValueError("Expected exactly probability and reason fields.")
    p = obj["probability"]
    if isinstance(p, bool) or not isinstance(p, (int, float)):
        raise ValueError("Probability must be a number.")
    p = float(p)
    if not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("Probability must be strictly between zero and one.")
    reason = obj["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Reason must be nonempty text.")
    return p, reason.strip()[:1200]

def build_payload(question):
    question = validate_question(question)
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a probabilistic forecaster participating in a RESEARCH DRY RUN. "
                    "Return ONLY a JSON object with exactly two keys: "
                    "{\"probability\": 0.35, \"reason\": \"brief rationale\"}. "
                    "Probability is a decimal strictly between 0 and 1 for YES. "
                    "Do not invent sources, citations, research or current information. "
                    "No web search is available. Acknowledge uncertainty and potential "
                    "outdated information in the reason. Never treat the forecast as resolved."
                ),
            },
            {"role": "user", "content": "Give a YES probability for this future binary question: " + question},
        ],
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }

def markdown_escape(s):
    return s.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")

def main():
    question = os.environ.get("FORECAST_QUESTION", "")
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    try:
        payload = build_payload(question)
    except ValueError as exc:
        print(f"Invalid question: {exc}", file=sys.stderr)
        return 2
    if not key:
        print("No OPENROUTER_API_KEY secret; no request sent.", file=sys.stderr)
        return 2
    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/pencil-source/metac-bot-template",
            "X-Title": "PencilForecast One-shot Dry Run",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=50) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"Free-only API call refused: HTTP {exc.code}. No fallback.", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Free-only API call failed: {type(exc).__name__}. No fallback.", file=sys.stderr)
        return 1

    try:
        message = data["choices"][0]["message"]
        p, reason = parse_forecast(message.get("content"))
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        print(f"Forecast parsing failed: {exc}", file=sys.stderr)
        return 1

    used = str(data.get("model") or "not reported")
    cost = (data.get("usage") or {}).get("cost")
    cost_label = "not reported" if cost is None else str(cost)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output = (
        "## One-shot research forecast (NOT submitted to Metaculus)\n\n"
        f"- **UTC recording time:** {timestamp}\n"
        f"- **Question:** {markdown_escape(question)}\n"
        f"- **P(YES):** {p:.1%}\n"
        f"- **P(NO):** {1-p:.1%}\n"
        f"- **Requested model:** {MODEL}\n"
        f"- **Served model:** {markdown_escape(used)}\n"
        f"- **Provider-reported usage cost (USD):** {markdown_escape(cost_label)}\n"
        f"- **Reason (no live research):** {markdown_escape(reason)}\n\n"
        "This is a single uncalibrated AI guess, not a proof of prediction skill or tournament eligibility.\n"
    )
    # Preserve the pre-outcome forecast and the exact served model for later scoring.
    # GitHub Actions uploads this JSON as a run artifact; it is not a repository commit.
    record = {
        "schema_version": 1,
        "forecast_at_utc": timestamp,
        "question": question,
        "p_yes": p,
        "p_no": 1 - p,
        "baseline_p_yes": 0.5,
        "model_version": "free-binary-v0.2",
        "requested_model": MODEL,
        "served_model": used,
        "provider_reported_cost_usd": cost,
        "research": "none",
        "outcome": None,
        "resolved_at_utc": None,
        "metaculus_submitted": False,
    }
    with open("forecast_record.json", "w", encoding="utf-8") as record_file:
        json.dump(record, record_file, indent=2, ensure_ascii=False)
    print("Forecast saved in forecast_record.json (download from workflow artifact).")
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(output)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
