"""Bounded public estate observation; never import or execute acquired source.

Extends the existing audit lane to every public SZL repository and public Hub
asset family. Exact-byte acquisition and syntax observations are not a complete
security review, model evaluation, deployment attestation or trading admission.
"""
from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import tomllib
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile

OUT = Path("finance-estate-audit")
HOSTS = frozenset({"api.github.com", "codeload.github.com", "huggingface.co",
                  "a-11-oy.com", "a11oy.net"})
MAX_API = 32 * 1024 * 1024
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
APP = re.compile(r"^szlholdings-[a-z0-9-]+(?:\.static)?\.hf\.space$")
TEXT = frozenset({".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".md", ".txt", ".html",
    ".css", ".cff", ".sh", ".ps1", ".sql", ".pine", ".pinescript", ".lean"})


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def allowed(url: str) -> bool:
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.port in (None, 443)
                and not p.username and not p.password and not p.fragment
                and (p.hostname in HOSTS or APP.fullmatch(p.hostname or "") is not None))
    except ValueError:
        return False


class Redirect(HTTPRedirectHandler):
    # Auditing does not need an implicit redirect. Record a refused destination
    # rather than forwarding credentials or draining an uncontrolled response.
    def http_error_302(self, req, fp, code, msg, headers):
        fp.close()
        raise ValueError("redirect denied")

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def get(url: str, limit: int = MAX_API) -> tuple[bytes, dict]:
    if not allowed(url):
        raise ValueError("destination denied")
    headers = {"User-Agent": "SZL-public-estate-observer/2.0", "Accept": "application/json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and urlsplit(url).hostname == "api.github.com":
        headers["Authorization"] = "Bearer " + token
    deadline = time.monotonic() + 90
    with build_opener(ProxyHandler({}), Redirect()).open(Request(url, headers=headers), timeout=25) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and (not declared.isdigit() or int(declared) > limit):
            raise ValueError("declared response exceeds bound")
        parts, count = [], 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("response deadline")
            part = response.read(min(65536, limit + 1 - count))
            if not part:
                break
            count += len(part)
            if count > limit:
                raise ValueError("response exceeds bound")
            parts.append(part)
        return b"".join(parts), dict(response.headers)


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(value, bytes):
        value = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    path.write_bytes(value)


def json_get(url: str):
    return json.loads(get(url)[0])


def paged(url: str) -> list:
    result, visited = [], set()
    origin = urlsplit(url).hostname
    for _ in range(20):
        if url in visited or urlsplit(url).hostname != origin:
            raise ValueError("pagination origin or cycle")
        visited.add(url)
        raw, headers = get(url)
        batch = json.loads(raw)
        if not isinstance(batch, list):
            raise ValueError("collection must be a list")
        result.extend(batch)
        link = headers.get("Link", headers.get("link", ""))
        following = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if not following:
            return result
        url = following.group(1)
    raise ValueError("pagination limit")


def member_path(name: str) -> PurePosixPath:
    p = PurePosixPath(name)
    if any(x in ("", ".", "..") for x in name.split("/")):
        raise ValueError("unsafe archive path")
    if p.is_absolute() or len(p.parts) < 2 or any(x in ("..", ".") for x in p.parts):
        raise ValueError("unsafe archive path")
    if any(x in name for x in ("\\", ":", "\x00")):
        raise ValueError("unsafe archive path")
    return PurePosixPath(*p.parts[1:])


def text_file(path: PurePosixPath) -> bool:
    return path.suffix.lower() in TEXT or path.name.lower().startswith(("license", "notice", "dockerfile", "makefile", "agents"))


def syntax(path: str, raw: bytes) -> dict:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix not in {".py", ".json", ".toml"}:
        return {"state": "NOT_EVALUATED"}
    try:
        if suffix == ".py":
            ast.parse(raw, filename=path)
        elif suffix == ".json":
            json.loads(raw)
        else:
            tomllib.loads(raw.decode("utf-8"))
        return {"state": "PARSED", "semantic_review": False}
    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError) as exc:
        return {"state": "PARSE_EXCEPTION", "error_type": type(exc).__name__,
                "line": getattr(exc, "lineno", None), "requires_review": True}


def acquire_zip(raw: bytes, entries: dict, root: Path) -> dict:
    records, seen, expanded = [], set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.infolist()) > 50000:
            raise ValueError("archive member count")
        for member in archive.infolist():
            if member.is_dir():
                continue
            path = member_path(member.filename)
            key = str(path)
            if key in seen:
                raise ValueError("duplicate archive member")
            seen.add(key)
            expected = entries.get(key)
            record = {"path": key, "state": "OMITTED"}
            if expected is None:
                record["reason"] = "NOT_IN_OBSERVED_TREE"
            elif stat.S_ISLNK(member.external_attr >> 16) or expected.get("mode") == "120000":
                record["reason"] = "SYMLINK"
            elif not text_file(path):
                record["reason"] = "NON_TEXT_POLICY"
            elif member.file_size > MAX_FILE:
                record["reason"] = "FILE_BYTE_LIMIT"
            else:
                expanded += member.file_size
                if expanded > MAX_EXPANDED:
                    raise ValueError("expanded text limit")
                with archive.open(member) as stream:
                    body = stream.read(MAX_FILE + 1)
                if len(body) != member.file_size or len(body) > MAX_FILE:
                    raise ValueError("archive member length")
                actual = blob_sha(body)
                if actual != expected.get("sha"):
                    raise ValueError("tree/blob mismatch")
                try:
                    body.decode("utf-8")
                except UnicodeDecodeError:
                    record["reason"] = "NON_UTF8"
                else:
                    save(root / key, body)
                    record.update(state="ACQUIRED", blob_sha=actual, sha256=sha256(body),
                                  bytes=len(body), syntax=syntax(key, body))
            records.append(record)
    for key in sorted(set(entries) - seen):
        records.append({"path": key, "state": "OMITTED", "reason": "NOT_IN_ARCHIVE"})
    return {"status": "ACQUIRED_BOUNDED_TEXT", "archive_sha256": sha256(raw),
            "archive_bytes": len(raw), "text_files_acquired": sum(x["state"] == "ACQUIRED" for x in records),
            "files": records, "code_executed": False, "manual_review_complete": False}


def inspect_repo(item: dict) -> dict:
    repo = item["full_name"]
    if not REPO.fullmatch(repo) or item.get("private") is not False:
        raise ValueError("public repository identity required")
    folder = OUT / "github" / repo
    record = {"repo": repo, "archived": item["archived"], "visibility": "public", "status": "UNAVAILABLE"}
    try:
        branch = quote(item["default_branch"], safe="")
        commit = json_get(f"https://api.github.com/repos/{repo}/commits/{branch}")
        sha = commit["sha"]
        if not SHA.fullmatch(sha):
            raise ValueError("commit identity")
        record["sha"] = sha
        save(folder / "commit.json", commit)
        tree = json_get(f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1")
        save(folder / "tree.json", tree)
        entries = {x["path"]: x for x in tree.get("tree", []) if x.get("type") == "blob"}
        record.update(status="TREE_OBSERVED", tree_truncated=bool(tree.get("truncated")), files_listed=len(entries))
        collect = repo.startswith("szl-holdings/") or item["name"] not in {"market-trackers-data", "cla-signatures"}
        if collect and not tree.get("truncated"):
            try:
                raw, _ = get(f"https://codeload.github.com/{repo}/zip/{sha}", MAX_ARCHIVE)
                acquired = acquire_zip(raw, entries, folder / "source")
                save(folder / "files.json", acquired.pop("files"))
                record["snapshot"] = acquired
            except Exception as exc:
                record["snapshot"] = {"status": "UNAVAILABLE", "error_type": type(exc).__name__}
        else:
            record["snapshot"] = {"status": "NOT_ACQUIRED", "reason": "TRUNCATED_TREE_OR_EXCLUDED_REFERENCE_DATA"}
        end = json_get(f"https://api.github.com/repos/{repo}/commits/{branch}")["sha"]
        record.update(head_at_readback=end, head_moved=end != sha)
    except Exception as exc:
        record["error_type"] = type(exc).__name__
    save(folder / "inventory.json", record)
    return record


def observe(url: str, *, json_expected: bool = True) -> dict:
    record = {"url": url, "observed_at": now(), "state": "UNAVAILABLE"}
    try:
        raw, _ = get(url, 4 * 1024 * 1024)
        save(OUT / "observations" / (sha256(url.encode()) + ".txt"), raw)
        record.update(state="HTTP_REACHABLE", bytes=len(raw), sha256=sha256(raw))
        try:
            record["json"] = json.loads(raw)
        except (ValueError, UnicodeError):
            if json_expected:
                record["state"] = "EXPECTED_JSON_NOT_OBSERVED"
    except Exception as exc:
        record["error_type"] = type(exc).__name__
    return record


def inspect_hub(kind: str, item: dict) -> dict:
    repo = item.get("id", "")
    if not REPO.fullmatch(repo) or repo.split("/")[0].upper() != "SZLHOLDINGS":
        raise ValueError("Hub author identity")
    record = observe(f"https://huggingface.co/api/{kind}/{repo}")
    info = record.get("json", {})
    sha = info.get("sha", "") if isinstance(info, dict) else ""
    record["repo_type"] = kind
    record["repo_id"] = repo
    if SHA.fullmatch(sha):
        try:
            tree = paged(f"https://huggingface.co/api/{kind}/{repo}/tree/{sha}?recursive=true&expand=false")
            save(OUT / "hub" / kind / repo / "tree.json", tree)
            record["files_listed"] = len([x for x in tree if x.get("type") == "file"])
        except Exception as exc:
            record["tree_error_type"] = type(exc).__name__
        record["card"] = observe(f"https://huggingface.co/{'' if kind == 'models' else kind + '/'}{repo}/raw/{sha}/README.md", json_expected=False)
    if kind == "spaces":
        subdomain = info.get("subdomain", "") if isinstance(info, dict) else ""
        host = subdomain if subdomain.endswith(".hf.space") else subdomain + ".hf.space"
        if APP.fullmatch(host):
            record["runtime_probes"] = [observe("https://" + host + path, json_expected=path != "/")
                for path in ("/", "/api/build-info", "/.well-known/szl-source.json")]
        else:
            record["runtime_probe_state"] = "SUBDOMAIN_UNOBSERVED"
    return record


def main() -> None:
    if OUT.exists():
        raise SystemExit("Refusing to mix observation directories")
    OUT.mkdir()
    report = {"schema": "szl.finance.estate-observation/v2", "started_at": now(),
        "collector_revision": os.environ.get("GITHUB_SHA", "UNBOUND"),
        "scope": "Anonymous-public Hub and public GitHub repositories only; private estate remains unobserved",
        "production_admitted": False, "code_executed": False, "manual_all_file_audit_complete": False}
    repositories = []
    for org in ("LuxAlgo", "szl-holdings"):
        batch = paged(f"https://api.github.com/orgs/{org}/repos?type=public&per_page=100")
        save(OUT / (org + "-repositories.json"), batch)
        repositories.extend(batch)
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["repositories"] = list(pool.map(inspect_repo, repositories))
    report["hub"] = {}
    for kind in ("spaces", "models", "datasets", "collections", "buckets"):
        url = (f"https://huggingface.co/api/buckets/SZLHOLDINGS" if kind == "buckets" else
            "https://huggingface.co/api/collections?owner=SZLHOLDINGS&limit=100" if kind == "collections" else
            f"https://huggingface.co/api/{kind}?author=SZLHOLDINGS&limit=100&full=true")
        try:
            items = paged(url)
            save(OUT / "hub" / (kind + ".json"), items)
            summary = {"state": "PUBLIC_COLLECTION_OBSERVED", "count": len(items)}
            if kind in ("spaces", "models", "datasets"):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    summary["details"] = list(pool.map(lambda item: inspect_hub(kind, item), items))
            elif kind == "collections":
                summary["full_member_observations"] = []
                for item in items:
                    slug = item.get("slug", "")
                    if REPO.fullmatch(slug):
                        summary["full_member_observations"].append(observe(f"https://huggingface.co/api/collections/{slug}"))
            else:
                summary["bucket_object_contents"] = "NOT_ACQUIRED"
            report["hub"][kind] = summary
        except Exception as exc:
            report["hub"][kind] = {"state": "UNAVAILABLE", "error_type": type(exc).__name__}
    report["domains"] = [observe(url, json_expected=False) for url in ("https://a-11-oy.com/", "https://a11oy.net/")]
    report["finished_at"] = now()
    save(OUT / "report.json", report)
    save(OUT / "SHA256SUMS.json", {str(p.relative_to(OUT)): sha256(p.read_bytes()) for p in sorted(OUT.rglob("*")) if p.is_file()})
    print(json.dumps({"repositories": len(repositories), "public_hub": {k: {a: v[a] for a in ("state", "count") if a in v} for k, v in report["hub"].items()}, "production_admitted": False}))


if __name__ == "__main__":
    main()
