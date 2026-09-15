"""Read-only public evidence acquisition. No acquired code is executed.

A collected ledger is NOT a verified ledger, and a reachable Space is NOT a
qualified trading agent. Private assets, credentials and broker APIs are absent.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

import collect_finance_estate as base

OUT = Path("finance-release-readback")
QUANT = "szl-holdings/szl-quant"
QUANT_SOURCE = "0a18eea4c0ced5543e0536bf84b3cb47b88ecc0f"
QUANT_LEDGER = "7284cbc41479486c9d9de5c663f7c7972cb578b4"
A11OY = "szl-holdings/a11oy"
A11OY_CANDIDATE = "ef71ef0e8898f8cc85a947df0f3b7eb6503d0f85"
A11OY_FILES = (
    ".github/workflows/finance-source-contracts.yml", "a11oy_markets.py",
    "docs/FINANCE_SOURCE_BACKEND.md", "scripts/finance_source_smoke.py",
    "scripts/hf_finance_read_proxy.py", "scripts/hf_publish_vertical_flagships_v4_impl.py",
    "tests/test_finance_bls_missing.py", "tests/test_finance_route_registration.py",
    "tests/test_finance_source_contracts.py", "tests/test_hf_publish_vertical_flagships_v4.py",
    "verticals/puriq-markets/runtime/__init__.py", "verticals/puriq-markets/runtime/routes.py",
    "verticals/puriq-markets/runtime/sources.py", "verticals/puriq-markets/runtime/transport.py",
)
base.ALLOW = base.ALLOW | {"szlholdings-a11oy.hf.space"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def acquire_zip(revision: str, name: str) -> dict:
    url = f"https://codeload.github.com/{QUANT}/zip/{revision}"
    record = {"repository": QUANT, "revision": revision, "url": url, "observed_at": now()}
    try:
        raw, _ = base.get(url, 64 * 1024 * 1024)
        base.save(OUT / name, raw)
        record.update(state="ACQUIRED_NOT_EXECUTED", sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    except Exception as exc:
        record.update(state="UNAVAILABLE", error_type=type(exc).__name__)
    return record


def acquire_candidate() -> dict:
    report = {"repository": A11OY, "revision": A11OY_CANDIDATE, "scope": "14 named finance integration files only", "files": []}
    tree = base.json_get(f"https://api.github.com/repos/{A11OY}/git/trees/{A11OY_CANDIDATE}?recursive=1")
    if tree.get("truncated") is not False:
        raise ValueError("candidate tree incomplete")
    by_path = {e["path"]: e for e in tree["tree"] if e["type"] == "blob"}
    for path in A11OY_FILES:
        row = {"path": path}
        try:
            entry = by_path[path]
            if entry.get("size", 0) > 2 * 1024 * 1024:
                raise ValueError("candidate blob too large")
            blob = base.json_get(f"https://api.github.com/repos/{A11OY}/git/blobs/{entry['sha']}")
            if blob.get("encoding") != "base64":
                raise ValueError("unexpected encoding")
            raw = base64.b64decode(blob["content"])
            raw.decode("utf-8")
            actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if actual != entry["sha"]:
                raise ValueError("blob identity mismatch")
            base.save(OUT / "a11oy-pr2176" / path, raw)
            row.update(state="ACQUIRED_NOT_EXECUTED", blob_sha=actual, sha256=hashlib.sha256(raw).hexdigest())
        except Exception as exc:
            row.update(state="UNAVAILABLE", error_type=type(exc).__name__)
        report["files"].append(row)
    return report


def observe(url: str) -> dict:
    row = {"url": url, "observed_at": now()}
    try:
        raw, headers = base.get(url, 4 * 1024 * 1024)
        digest = hashlib.sha256(raw).hexdigest()
        relative = "observations/" + hashlib.sha256(url.encode()).hexdigest() + ".txt"
        base.save(OUT / relative, raw)
        row.update(state="HTTP_200_OBSERVED", sha256=digest, bytes=len(raw), body_file=relative,
                   content_type=headers.get("Content-Type", headers.get("content-type", "")))
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                row["json"] = value
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    except Exception as exc:
        row.update(state="UNAVAILABLE", error_type=type(exc).__name__)
        code = getattr(exc, "code", None)
        if isinstance(code, int):
            row["http_status"] = code
    return row


def main() -> None:
    if OUT.exists():
        raise SystemExit("Refusing mixed observations")
    OUT.mkdir()
    report = {"schema": "szl.finance.release-readback/v1", "started_at": now(),
              "collector_revision": os.getenv("GITHUB_SHA", "UNBOUND"),
              "public_only": True, "downloaded_code_executed": False,
              "ledger_verified": False, "production_admitted": False,
              "live_trading_enabled": False, "capital_transferred": False}
    report["quant_source"] = acquire_zip(QUANT_SOURCE, "quant-source.zip")
    report["quant_ledger"] = acquire_zip(QUANT_LEDGER, "quant-ledger.zip")
    try:
        report["a11oy_candidate"] = acquire_candidate()
    except Exception as exc:
        report["a11oy_candidate"] = {"state": "UNAVAILABLE", "error_type": type(exc).__name__}
    report["observations"] = []
    for space in ("finance", "a11oy", "vertical-services"):
        hub = observe(f"https://huggingface.co/api/spaces/SZLHOLDINGS/{space}")
        report["observations"].append(hub)
        sha = hub.get("json", {}).get("sha", "")
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            for path in ("README.md", "Dockerfile", "app.py", "build-receipt.json"):
                report["observations"].append(observe(f"https://huggingface.co/spaces/SZLHOLDINGS/{space}/raw/{sha}/{path}"))
        for path in ("/healthz", "/api/build-info", "/.well-known/szl-source.json"):
            report["observations"].append(observe(f"https://szlholdings-{space}.hf.space{path}"))
    for url in (
        "https://szlholdings-finance.hf.space/research",
        "https://szlholdings-finance.hf.space/api/finance/providers",
        "https://szlholdings-finance.hf.space/api/live",
        "https://szlholdings-a11oy.hf.space/api/a11oy/v1/finance/providers",
        "https://a-11-oy.com/", "https://a11oy.net/",
    ):
        report["observations"].append(observe(url))
    report["branch_readback"] = {}
    for repo, branch, expected in ((QUANT,"main",QUANT_SOURCE),(QUANT,"ledger",QUANT_LEDGER),(A11OY,"feat/finance-market-data-20260915",A11OY_CANDIDATE)):
        key = repo + ":" + branch
        try:
            value = base.json_get(f"https://api.github.com/repos/{repo}/git/ref/heads/{branch}")["object"]["sha"]
            report["branch_readback"][key] = {"sha": value, "matches_acquired_revision": value == expected}
        except Exception as exc:
            report["branch_readback"][key] = {"state": "UNAVAILABLE", "error_type": type(exc).__name__}
    report["finished_at"] = now()
    base.save(OUT / "report.json", report)
    base.save(OUT / "SHA256SUMS.json", {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob("*")) if p.is_file()})
    print(json.dumps({"output": str(OUT), "quant_source": report["quant_source"]["state"],
                      "quant_ledger": report["quant_ledger"]["state"], "ledger_verified": False}))
    if report["quant_source"]["state"] == "UNAVAILABLE" or report["quant_ledger"]["state"] == "UNAVAILABLE":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
