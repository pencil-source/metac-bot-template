#!/usr/bin/env python3
"""Read-only historical forecast audit from GitHub Actions artifacts and Metaculus.

No OpenRouter requests, Metaculus submissions, paid services or schedule.
Only explicit official YES/NO resolutions visible to this bot account are scored.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import urllib.error
import urllib.request
from zipfile import ZipFile, BadZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forecastlab_v03 as lab

GITHUB_API = "https://api.github.com"
REPO = "pencil-source/metac-bot-template"
ALLOWED_ARTIFACTS = {"pencil-forecast-research", "pencil-forecast-v03-smoke"}
MAX_ZIP_BYTES = 2_000_000
MAX_JSONL_BYTES = 500_000
MAX_RUNS = 35

def github_get_json(path, token):
    if not path.startswith(f"/repos/{REPO}/"):
        raise ValueError("Unexpected GitHub API path")
    return lab.request_json(
        GITHUB_API+path,
        headers={"Authorization":"Bearer "+token,
                 "Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28"})

def github_get_artifact_zip(artifact_id, token):
    """Download only GitHub-signed artifact ZIPs; never forward GitHub credentials.

    GitHub REST returns a 302 redirect to an object store. Sending the GitHub
    Bearer token to that second host may trigger HTTP 401 and leaks a credential.
    Handle that redirect explicitly and request the signed URL WITHOUT auth.
    """
    if not isinstance(artifact_id, int) or artifact_id <= 0:
        raise ValueError("Invalid artifact ID")
    url = f"{GITHUB_API}/repos/{REPO}/actions/artifacts/{artifact_id}/zip"
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "PencilForecastResearch/0.3",
    }

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    signed_url = None
    try:
        try:
            response = opener.open(
                urllib.request.Request(url, headers=headers, method="GET"),
                timeout=35)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                raise RuntimeError(f"Artifact API rejected download (HTTP {exc.code})") from None
            signed_url = exc.headers.get("Location")
            exc.close()
            if not signed_url:
                raise RuntimeError("GitHub artifact redirect had no Location")
            parsed = urlsplit(signed_url)
            host = (parsed.hostname or "").lower()
            allowed = (
                host.endswith(".blob.core.windows.net")
                or host.endswith(".actions.githubusercontent.com")
                or host.endswith(".githubusercontent.com")
                or host in ("github.com", "api.github.com")
            )
            if parsed.scheme != "https" or not allowed or parsed.username or parsed.password:
                raise RuntimeError("Unexpected artifact redirect destination; refusing")
            # Auth is intentionally omitted for the short-lived signed redirect URL.
            response = urllib.request.urlopen(
                urllib.request.Request(
                    signed_url, headers={"User-Agent":"PencilForecastResearch/0.3"},
                    method="GET"), timeout=35)
        with response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ZIP_BYTES:
                raise ValueError("Artifact exceeds size limit")
            data = response.read(MAX_ZIP_BYTES + 1)
    except urllib.error.HTTPError as exc:
        host = urlsplit(exc.url).hostname or "unknown"
        # No signed URL, query string, token or response body is ever logged.
        raise RuntimeError(f"Artifact download rejected by {host} (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Artifact download failed: {type(exc).__name__}") from None
    if len(data) > MAX_ZIP_BYTES:
        raise ValueError("Artifact exceeds size limit")
    return data

def decode_forecasts(data):
    """Inspect only one named file; no zip extraction or filesystem traversal."""
    try:
        with ZipFile(BytesIO(data)) as zf:
            matches=[p for p in zf.infolist() if p.filename=="forecasts.jsonl"]
            if len(matches)!=1:
                return []
            info=matches[0]
            if info.file_size>MAX_JSONL_BYTES:
                raise ValueError("Forecast file exceeds safe size cap")
            text=zf.read(info).decode("utf-8")
    except (BadZipFile,UnicodeError):
        raise ValueError("Malformed artifact ZIP") from None
    rows=[]
    for line in text.splitlines():
        if not line.strip():continue
        row=json.loads(line)
        lab.validate_record(row)  # includes recorded time and SHA256
        rows.append(row)
    return rows

def load_history(token, max_runs=MAX_RUNS):
    """Return the EARLIEST recorded forecast per question (no cherry-picking)."""
    if not (1<=max_runs<=MAX_RUNS):
        raise ValueError("max_runs must be 1-35")
    resp=github_get_json(f"/repos/{REPO}/actions/runs?per_page=100",token)
    runs=resp.get("workflow_runs",[])
    if not isinstance(runs,list):
        raise RuntimeError("GitHub workflow run list not available")
    records=[]; problems=[]; checked=0
    for run in runs:
        if checked>=max_runs:
            break
        if run.get("status")!="completed" or run.get("conclusion")!="success":
            continue
        name=run.get("name","")
        if not ("PencilForecast v0.3 - research" in name or
                "PencilForecast v0.3 integration smoke test" in name):
            continue
        checked+=1
        try:
            arts=github_get_json(
                f"/repos/{REPO}/actions/runs/{int(run['id'])}/artifacts",token)
            for art in arts.get("artifacts", []):
                if art.get("name") not in ALLOWED_ARTIFACTS or art.get("expired"):
                    continue
                rows=decode_forecasts(github_get_artifact_zip(int(art["id"]),token))
                records.extend(rows)
        except (RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            # These exception messages contain only status codes/types, not URLs or keys.
            problems.append(f"run {run.get('id')}: {type(exc).__name__}: {str(exc)[:150]}")
    earliest={}
    for rec in records:
        key=rec["question_id"]
        when=lab.parse_time(rec["recorded_at_utc"])
        if key not in earliest or when < lab.parse_time(earliest[key]["recorded_at_utc"]):
            earliest[key]=rec
    selected=sorted(earliest.values(),key=lambda x:x["recorded_at_utc"])
    duplicates=len(records)-len(selected)
    return selected, {"runs_checked":checked,"records_read":len(records),
                      "duplicates_ignored":duplicates,"download_errors":problems}

def parse_resolution(q):
    if not isinstance(q,dict) or q.get("status")!="resolved":
        return None
    raw=q.get("resolution")
    if isinstance(raw,bool):
        # Metaculus official API may use booleans; accept only explicit boolean.
        outcome=1 if raw else 0
    elif isinstance(raw,(int,float)) and raw in (0,1):
        outcome=int(raw)
    elif isinstance(raw,str) and raw.lower() in ("yes","no"):
        outcome=1 if raw.lower()=="yes" else 0
    else:
        # Explicitly exclude ambiguous, annulled, hidden and unknown outcomes.
        return None
    when=lab.parse_time(q.get("actual_resolve_time"))
    if not when:return None
    return outcome,when.isoformat()

def check_metaculus_resolutions(records):
    """Use only Metaculus GET; absent/redacted official outcomes remain pending."""
    found=[]; pending=[]; errors=[]
    cache={}
    for rec in records:
        post_id=rec["post_id"]
        if post_id not in cache:
            try:
                cache[post_id]=lab.get_post(post_id)
            except (RuntimeError,ValueError) as exc:
                errors.append(f"post {post_id}: {type(exc).__name__}")
                cache[post_id]=None
        post=cache[post_id]
        q=post.get("question") if isinstance(post,dict) else None
        if not isinstance(q,dict) or q.get("id")!=rec["question_id"]:
            pending.append(rec)
            continue
        try:
            resolution=parse_resolution(q)
        except (ValueError,TypeError):
            resolution=None
        if resolution is None:
            pending.append(rec)
        else:
            outcome,when=resolution
            found.append({
                "question_id":str(rec["question_id"]),
                "outcome":"yes" if outcome==1 else "no",
                "resolved_at_utc":when,
                "verification_url":rec["source_url"],
            })
    return found,pending,errors

def save_csv(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=[
            "question_id","outcome","resolved_at_utc","verification_url"])
        w.writeheader()
        w.writerows(rows)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=Path("history_audit"))
    parser.add_argument("--max-runs",type=int,default=MAX_RUNS)
    args=parser.parse_args(argv)
    github_key=os.getenv("GITHUB_TOKEN","").strip()
    if not github_key:
        raise RuntimeError("GITHUB_TOKEN missing; no GitHub request made")
    records,meta=load_history(github_key,args.max_runs)
    args.out.mkdir(parents=True,exist_ok=True)
    lab.write_jsonl(args.out/"historical_forecasts.jsonl",records)
    outcomes,awaiting,errors=check_metaculus_resolutions(records)
    save_csv(args.out/"visible_official_resolutions.csv",outcomes)
    evaluated,pending=lab.score(records,outcomes)
    output=lab.report(evaluated,pending)
    summary=[
        "# PencilForecast history retrieval status",
        f"Runs checked: {meta['runs_checked']}",
        f"Forecasts read: {meta['records_read']}",
        f"Unique questions: {len(records)}",
        f"Repeated question forecasts excluded: {meta['duplicates_ignored']}",
        f"Visible official YES/NO outcomes: {len(evaluated)}",
        f"Still pending, hidden, or ambiguous: {len(pending)}",
        f"GitHub artifact read issues: {len(meta['download_errors'])}",
        f"Metaculus read issues: {len(errors)}",
        *[f"Artifact issue: {issue}" for issue in meta['download_errors']],
        "",
        "Not visible does NOT mean NO. No live tournament submission or paid inference.",
        "API account permissions can hide resolutions for questions without a posted forecast.",
        "SHA256 self-check is for accidental modification, not tamper-proof attestation.",
        "",
    ]
    message="\n".join(summary) + output
    (args.out/"history_audit.md").write_text(message,encoding="utf-8")
    lab.write_json(args.out/"audit_status.json",{
        "created_at_utc":lab.iso_now(),"runs":meta,"metaculus_errors":errors,
        "verified_resolved":len(evaluated),"pending":len(pending)})
    print(message)
    github_summary=os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary,"a",encoding="utf-8") as f:
            f.write(message)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError,ValueError,OSError) as exc:
        print("History audit failed: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
