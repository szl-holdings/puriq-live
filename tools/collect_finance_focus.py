"""Read-only focused acquisition after the bounded whole-estate inventory.

Never executes downloaded code, imports a publisher, installs dependencies,
uses broker credentials, or changes a provider resource.
"""
from __future__ import annotations
import base64
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
from datetime import datetime, timezone
import collect_finance_estate as base

OUT = Path('finance-focus-audit')
REVISION = '7bb46fd93da77431bd31b7d35b0b341fe240d2e4'
REPO = 'szl-holdings/a11oy'
base.ALLOW = base.ALLOW | {'registry.npmjs.org'}
PATTERN = re.compile(r'puriq|finance|quant_signals|a11oy_markets|a11oy_deva|vertical_flagships|hf_publish_lyte_enterprise|hf_existing_space_guard|hf_publish_source_guard|hf_publish_vertical_services')
EXACT = {'AGENTS.md', 'requirements.txt', 'requirements-test.txt', 'package.json', 'Dockerfile', '.github/workflows/hf-publish-vertical-flagships.yml'}


def acquire(entry):
    record = {'path':entry['path'], 'blob_sha':entry['sha']}
    try:
        blob = base.json_get(f'https://api.github.com/repos/{REPO}/git/blobs/{entry["sha"]}')
        if blob.get('encoding') != 'base64':
            raise ValueError('unexpected blob encoding')
        raw = base64.b64decode(blob['content'], validate=False)
        if len(raw) > base.MAX_MEMBER:
            raise ValueError('blob exceeds limit')
        raw.decode('utf-8')
        actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if actual != entry['sha']:
            raise ValueError('blob identity mismatch')
        safe = base.safe_member('root/' + entry['path'])
        base.save(OUT/'a11oy-source'/str(safe), raw)
        record.update(status='ACQUIRED',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    except Exception as exc:
        record.update(status='UNAVAILABLE', error_type=type(exc).__name__)
    return record


def main():
    if OUT.exists():
        raise SystemExit('Refusing mixed observations')
    OUT.mkdir()
    report = {'schema':'szl.finance.focus-observation/v1','observed_at':datetime.now(timezone.utc).isoformat(),
        'repository':REPO,'source_revision':REVISION,'code_executed':False,'production_admitted':False}
    tree = base.json_get(f'https://api.github.com/repos/{REPO}/git/trees/{REVISION}?recursive=1')
    if tree.get('truncated'):
        raise RuntimeError('incomplete source inventory')
    selected = [e for e in tree['tree'] if e['type']=='blob' and (e['path'] in EXACT or PATTERN.search(e['path'])) and base.text_file(Path(e['path'])) and e.get('size',0) <= base.MAX_MEMBER]
    if len(selected)>180:
        raise RuntimeError('focus selection exceeds explicit file budget')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        report['files']=list(pool.map(acquire,selected))
    report['head_at_readback']=base.json_get(f'https://api.github.com/repos/{REPO}/git/ref/heads/main')['object']['sha']
    report['head_matches_snapshot']=report['head_at_readback']==REVISION
    report['vela']={'version':'0.7.3','execution':'NOT_EXECUTED'}
    try:
        metadata=base.json_get('https://registry.npmjs.org/@luxalgo%2Fvela/0.7.3')
        base.save(OUT/'vela/npm-metadata.json',metadata)
        integrity=metadata['dist']['integrity']
        algorithm,encoded=integrity.split('-',1)
        if algorithm!='sha512':
            raise ValueError('expected registry sha512')
        raw,_=base.get(metadata['dist']['tarball'])
        if base64.b64encode(hashlib.sha512(raw).digest()).decode()!=encoded:
            raise ValueError('npm archive integrity mismatch')
        files=[]
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
            for name in ('package/dist/vela.global.min.js','package/LICENSE','package/NOTICE','package/package.json'):
                member=archive.getmember(name)
                if not member.isfile() or member.size>4*1024*1024:
                    raise ValueError('invalid distribution member')
                data=archive.extractfile(member).read(4*1024*1024+1)
                data.decode('utf-8')
                base.save(OUT/'vela'/Path(name).name,data)
                files.append({'path':Path(name).name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        report['vela'].update(status='ACQUIRED',archive_integrity=integrity,git_head=metadata.get('gitHead'),files=files)
    except Exception as exc:
        report['vela'].update(status='UNAVAILABLE',error_type=type(exc).__name__)
    base.OUT=OUT
    report['probes']=[base.observe_url(url) for url in (
        'https://szlholdings-finance.hf.space/api/live',
        'https://szlholdings-finance.hf.space/build-receipt.json',
        'https://szlholdings-vertical-services.hf.space/finance/healthz',
        'https://szlholdings-vertical-services.hf.space/api/verticals/finance/readiness',
    )]
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    base.save(OUT/'report.json',report)
    manifest={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file()}
    base.save(OUT/'SHA256SUMS.json',manifest)
    print(json.dumps({'files':len(selected),'failed':sum(x['status']!='ACQUIRED' for x in report['files']),'vela':report['vela']['status'],'production_admitted':False}))


if __name__=='__main__':
    main()
