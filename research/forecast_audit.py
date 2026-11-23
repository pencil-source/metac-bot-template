#!/usr/bin/env python3
"""Offline audit of pre-recorded binary forecasts. No network access or API keys."""
import argparse
import csv
from datetime import datetime
import math
from pathlib import Path
import random
import statistics

FIELDS = ("question_id", "forecast_at", "resolved_at", "prediction",
          "baseline", "outcome", "model_version", "cost_usd")

def timestamp(text):
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {text!r}") from exc
    if value.tzinfo is None:
        raise ValueError(f"Timezone is required: {text!r}")
    return value

def probability(raw, name, lineno):
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Row {lineno}: invalid {name}") from exc
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"Row {lineno}: {name} must be between 0 and 1")
    return value

def load_csv(path):
    complete, pending, seen = [], [], set()
    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("Missing columns: " + ", ".join(sorted(set(FIELDS) - set(reader.fieldnames or []))))
        for lineno, row in enumerate(reader, 2):
            qid = (row["question_id"] or "").strip()
            version = (row["model_version"] or "").strip()
            if not qid or not version:
                raise ValueError(f"Row {lineno}: question_id and model_version are mandatory")
            key = (qid, version)
            if key in seen:
                raise ValueError(f"Row {lineno}: duplicate question_id/model_version")
            seen.add(key)
            predicted = timestamp((row["forecast_at"] or "").strip())
            resolved = timestamp((row["resolved_at"] or "").strip())
            if predicted is None:
                raise ValueError(f"Row {lineno}: forecast_at is required")
            if resolved is not None and predicted >= resolved:
                raise ValueError(f"Row {lineno}: LEAKAGE: forecast is not earlier than resolution")
            p = probability(row["prediction"], "prediction", lineno)
            baseline = probability(row["baseline"], "baseline", lineno)
            try:
                cost = float(row["cost_usd"] or 0)
            except ValueError as exc:
                raise ValueError(f"Row {lineno}: invalid cost_usd") from exc
            if not math.isfinite(cost) or cost < 0:
                raise ValueError(f"Row {lineno}: cost_usd must be nonnegative and finite")
            record = dict(question_id=qid, p=p, baseline=baseline, cost=cost)
            outcome = (row["outcome"] or "").strip()
            if not outcome:
                if resolved:
                    raise ValueError(f"Row {lineno}: resolution time but no outcome")
                pending.append(record)
            else:
                if outcome not in ("0", "1") or resolved is None:
                    raise ValueError(f"Row {lineno}: resolved rows need outcome 0/1 and resolved_at")
                complete.append(dict(**record, y=int(outcome)))
    return complete, pending

def brier(p, y):
    return (p-y)**2

def log_loss(p, y):
    p = min(1 - 1e-12, max(1e-12, p))
    return -y*math.log(p) - (1-y)*math.log1p(-p)

def paired_interval(values, samples=4000, seed=20261124):
    """Naive percentile bootstrap; assumes observations are independent."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    results = sorted(statistics.fmean(values[rng.randrange(n)] for _ in range(n))
                     for _ in range(samples))
    return results[int(samples*.025)], results[int(samples*.975)]

def summarize(records, pending):
    lines = [
        "# Binary forecast audit (offline, experimental)",
        "",
        "This is NOT the official Metaculus Spot Peer Score.",
        "All forecasts must have been recorded before outcomes were known.",
        f"Resolved: {len(records)} | Pending: {len(pending)}",
        f"Reported inference cost: USD {sum(x['cost'] for x in records+pending):.2f}",
    ]
    if not records:
        lines += ["", "No resolved forecasts; no evidence of model performance."]
        return "\n".join(lines) + "\n"
    model_b = [brier(x["p"], x["y"]) for x in records]
    base_b = [brier(x["baseline"], x["y"]) for x in records]
    gain = [b-m for b, m in zip(base_b, model_b)]
    ci = paired_interval(gain)
    lines += [
        "",
        "## Results (lower loss is better)",
        f"Model Brier: {statistics.fmean(model_b):.5f}",
        f"Baseline Brier: {statistics.fmean(base_b):.5f}",
        f"Model log loss: {statistics.fmean(log_loss(x['p'],x['y']) for x in records):.5f}",
        f"Baseline log loss: {statistics.fmean(log_loss(x['baseline'],x['y']) for x in records):.5f}",
        f"Brier improvement over baseline: {statistics.fmean(gain):+.5f}",
        f"Naive paired bootstrap 95% CI: {tuple(round(x,5) for x in ci) if ci else 'N/A'}",
    ]
    lines += ["", "## Research gate",
              "Exploratory threshold: 100 independent resolved, forward-logged questions "
              "with positive lower CI bound.",
              "This is NOT proof of prize eligibility or profit.",
              "Gate: " + ("PROVISIONAL PASS" if len(records)>=100 and ci and ci[0]>0
                           else "NOT PASSED"),
              "",
              "Limitation: correlations by topic and time can make the bootstrap optimistic.",
              "Resolution timestamps alone cannot rule out earlier public information leakage."]
    return "\n".join(lines)+"\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path, help="CSV with fixed pre-outcome predictions")
    parser.add_argument("--out", type=Path, help="Optional Markdown output")
    args = parser.parse_args()
    complete, pending = load_csv(args.csv_file)
    output = summarize(complete, pending)
    print(output)
    if args.out:
        args.out.write_text(output, encoding="utf-8")

if __name__ == "__main__":
    main()
