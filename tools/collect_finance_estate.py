"""Bounded, read-only, public-source inventory. Never executes acquired code.

A successful collection is NOT a security review, deployment receipt, or trading
admission. Private repositories and omitted/oversize files remain unobserved.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
import zipfile

OUT = Path('finance-estate-audit')
ALLOW = frozenset({'api.github.com', 'codeload.github.com', 'huggingface.co',
    'szlholdings-finance.hf.space', 'szlholdings-vertical-services.hf.space',
    'a-11-oy.com', 'a11oy.net'})
MAX_BODY = 32 * 1024 * 1024
MAX_MEMBER = 2 * 1024 * 1024
MAX_EXPANDED = 80 * 1024 * 1024
SOURCE_REPOS = frozenset({'a11oy', 'puriq-live', 'vertical-services',
    'szl-quant', 'szl-quant-witness', 'szl-frontier', '.github', 'a11oy-net'})
TEXT_SUFFIXES = frozenset({'.py','.ts','.tsx','.js','.jsx','.mjs','.cjs','.html',
    '.css','.json','.yml','.yaml','.toml','.md','.txt','.cff','.sh','.ps1','.sql','.pinescript','.pine'})
FINANCE = re.compile(r'finance|puriq|polymarket|market|trading|broker|alpaca|quant', re.I)
SHA = re.compile(r'^[0-9a-f]{40}$')


def allowed_url(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname in ALLOW and p.port in (None,443) and not p.username and not p.password


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError('redirect outside public allowlist')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header('Authorization')
        return redirected


def get(url: str, limit: int = MAX_BODY) -> tuple[bytes, dict]:
    if not allowed_url(url):
        raise ValueError('URL outside public allowlist')
    headers = {'User-Agent': 'SZL-public-finance-audit/1.0', 'Accept': 'application/json'}
    # Credential never leaves api.github.com and is stripped on every redirect.
    token = os.environ.get('GITHUB_TOKEN')
    if token and urllib.parse.urlsplit(url).hostname == 'api.github.com':
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=headers, method='GET')
    with urllib.request.build_opener(PublicRedirect()).open(req, timeout=25) as res:
        if res.headers.get('Content-Length') and int(res.headers['Content-Length']) > limit:
            raise ValueError('declared body exceeds bound')
        body = res.read(limit + 1)
        if len(body) > limit:
            raise ValueError('body exceeds bound')
        return body, dict(res.headers)


def json_get(url: str):
    return json.loads(get(url)[0])


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(data, bytes):
        data = (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    path.write_bytes(data)


def safe_member(name: str) -> PurePosixPath:
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('unsafe archive member')
    if len(p.parts) < 2:
        raise ValueError('archive root only')
    return PurePosixPath(*p.parts[1:])


def text_file(path: PurePosixPath) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.lower().startswith(('license','notice','dockerfile','makefile','agents'))


def snapshot(repo: str, sha: str, root: Path) -> dict:
    body, _ = get(f'https://codeload.github.com/{repo}/zip/{sha}')
    count = 0
    expanded = 0
    omitted = []
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        if len(archive.infolist()) > 50000:
            raise ValueError('archive member count exceeds bound')
        for member in archive.infolist():
            if member.is_dir():
                continue
            path = safe_member(member.filename)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or member.file_size > MAX_MEMBER or not text_file(path):
                omitted.append(str(path))
                continue
            expanded += member.file_size
            if expanded > MAX_EXPANDED:
                raise ValueError('expanded archive exceeds bound')
            raw = archive.read(member)
            try:
                raw.decode('utf-8')
            except UnicodeDecodeError:
                omitted.append(str(path))
                continue
            save(root / str(path), raw)
            count += 1
    return {'download_sha256': hashlib.sha256(body).hexdigest(),
        'download_bytes':len(body), 'text_files_acquired':count,
        'omitted_files':omitted, 'code_executed':False, 'manual_review_complete':False}


def inventory_org(org: str) -> list:
    result = []
    for page in range(1, 21):
        batch = json_get(f'https://api.github.com/orgs/{org}/repos?type=public&per_page=100&page={page}')
        if not isinstance(batch,list):
            raise ValueError('invalid repository collection')
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise ValueError('repository pagination exceeded bound')


def inspect_repo(item: dict) -> dict:
    repo = item['full_name']
    folder = OUT / 'github' / repo
    result = {'repo':repo, 'archived':item['archived'], 'visibility':'public',
        'default_branch':item['default_branch'], 'description':item.get('description'),
        'license_metadata':item.get('license'), 'status':'UNOBSERVED'}
    try:
        branch = urllib.parse.quote(item['default_branch'],safe='')
        commit = json_get(f'https://api.github.com/repos/{repo}/commits/{branch}')
        sha = commit['sha']
        if not SHA.fullmatch(sha):
            raise ValueError('invalid commit identity')
        result['sha'] = sha
        save(folder / 'commit.json',commit)
        tree = json_get(f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1')
        save(folder / 'tree.json',tree)
        blobs = [entry for entry in tree.get('tree',[]) if entry.get('type') == 'blob']
        result.update(status='TREE_OBSERVED', tree_truncated=bool(tree.get('truncated')),
            files_listed=len(blobs), finance_paths=[x['path'] for x in blobs if FINANCE.search(x['path'])])
        full = repo.startswith('LuxAlgo/') and item['name'] not in {'market-trackers-data','cla-signatures'}
        full = full or (repo.startswith('szl-holdings/') and item['name'] in SOURCE_REPOS)
        if full:
            try:
                result['snapshot'] = snapshot(repo,sha,folder/'source')
            except Exception as exc:
                result['snapshot'] = {'status':'UNAVAILABLE', 'error_type':type(exc).__name__}
        else:
            result['snapshot'] = {'status':'NOT_REQUESTED', 'reason':'tree inventory only; data, non-finance or administration repository'}
        end = json_get(f'https://api.github.com/repos/{repo}/commits/{branch}')['sha']
        result['head_at_readback'] = end
        result['head_moved_during_collection'] = end != sha
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['status'] = 'UNAVAILABLE'
    save(folder / 'inventory.json',result)
    return result


def hf_list(kind: str) -> list:
    url = f'https://huggingface.co/api/{kind}?author=SZLHOLDINGS&limit=100&full=true'
    items = []
    for _ in range(20):
        raw, headers = get(url)
        batch = json.loads(raw)
        if not isinstance(batch,list):
            raise ValueError('invalid Hub collection')
        items.extend(batch)
        link = headers.get('Link',headers.get('link',''))
        following = re.search(r'<([^>]+)>;\s*rel="next"',link)
        if not following:
            return items
        url = following.group(1)
        if urllib.parse.urlsplit(url).hostname != 'huggingface.co':
            raise ValueError('invalid Hub pagination origin')
    raise ValueError('Hub pagination exceeded bound')


def observe_url(url: str) -> dict:
    record = {'url':url,'observed_at':datetime.now(timezone.utc).isoformat()}
    try:
        body,_ = get(url,4*1024*1024)
        record.update(status='REACHABLE', sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        save(OUT/'observations'/(hashlib.sha256(url.encode()).hexdigest()+'.txt'),body)
        try:
            record['json'] = json.loads(body)
        except (json.JSONDecodeError,UnicodeDecodeError):
            pass
    except Exception as exc:
        record.update(status='UNAVAILABLE',error_type=type(exc).__name__)
    return record


def main() -> None:
    if OUT.exists():
        raise SystemExit('Refusing to mix observations with an existing output directory')
    OUT.mkdir()
    report = {'schema':'szl.finance.estate-observation/v1',
        'started_at':datetime.now(timezone.utc).isoformat(),
        'collector_revision':os.environ.get('GITHUB_SHA','UNBOUND'),
        'scope':'public repositories and public Hub assets; not a private-estate audit',
        'trading_enabled':False,'production_admitted':False,'manual_all_file_audit_complete':False}
    repos = []
    for org in ('LuxAlgo','szl-holdings'):
        batch = inventory_org(org)
        save(OUT/(org+'-repositories.json'),batch)
        repos.extend(batch)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        report['repositories'] = list(pool.map(inspect_repo,repos))
    report['hub'] = {}
    for kind in ('spaces','models','datasets'):
        try:
            items = hf_list(kind)
            save(OUT/'hub'/(kind+'.json'),items)
            report['hub'][kind] = {'status':'PUBLIC_COLLECTION_OBSERVED','count':len(items)}
        except Exception as exc:
            report['hub'][kind] = {'status':'UNAVAILABLE','error_type':type(exc).__name__}
    report['observations'] = []
    for space in ('finance','vertical-services'):
        url = f'https://huggingface.co/api/spaces/SZLHOLDINGS/{space}'
        observed = observe_url(url)
        report['observations'].append(observed)
        sha = observed.get('json',{}).get('sha','')
        if SHA.fullmatch(sha):
            for path in ('README.md','Dockerfile','app.py','requirements.txt'):
                report['observations'].append(observe_url(f'https://huggingface.co/spaces/SZLHOLDINGS/{space}/raw/{sha}/{path}'))
        for path in ('/','/healthz','/api/build-info','/.well-known/szl-source.json'):
            report['observations'].append(observe_url(f'https://szlholdings-{space}.hf.space{path}'))
    for origin in ('https://a-11-oy.com','https://a11oy.net'):
        report['observations'].append(observe_url(origin+'/'))
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    save(OUT/'report.json',report)
    manifest = {str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SHA256SUMS.json',manifest)
    print(json.dumps({'repositories_observed':len(repos),'output':str(OUT),
        'unavailable_trees':sum(x['status']=='UNAVAILABLE' for x in report['repositories']),
        'hub':report['hub'],'production_admitted':False},indent=2))


if __name__ == '__main__':
    main()
