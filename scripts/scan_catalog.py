"""Reproducible public snapshot publisher. Does not access private application data."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.catalog import scan_sources
from server.core import is_month_end


def catalog_delta(old, new):
    before = {r['id']:r for r in old.get('skills', [])}
    after = {r['id']:r for r in new['skills']}
    report = {'generated_at':new.get('generated_at'), 'added':sorted(after.keys()-before.keys()),
              'removed':sorted(before.keys()-after.keys()), 'changed':[], 'version_changes':[],
              'dependency_changes':[], 'license_changes':[], 'errors':new.get('errors', [])}
    for identity in sorted(before.keys() & after.keys()):
        a, b = before[identity], after[identity]
        if a.get('commit') != b.get('commit'):
            report['version_changes'].append(identity)
        if any(a.get(k) != b.get(k) for k in ('body', 'bundle', 'bundle_encodings')):
            report['changed'].append(identity)
        if any(a.get(k) != b.get(k) for k in ('dependencies', 'compatibility')):
            report['dependency_changes'].append(identity)
        if a.get('license') != b.get('license'):
            report['license_changes'].append(identity)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--month-end-only', action='store_true')
    args = parser.parse_args()
    if args.month_end_only and not is_month_end(datetime.now(timezone.utc)):
        print('Not month end in Asia/Shanghai; skipped.')
        return
    directory = ROOT / 'catalog'
    result = scan_sources(json.loads((directory / 'sources.json').read_text(encoding='utf-8')))
    if not result['complete_repos']:
        print(json.dumps({'status':'failed','errors':result['errors']}, ensure_ascii=False))
        raise SystemExit(1)
    old = json.loads((directory / 'snapshot.json').read_text(encoding='utf-8')) if (directory / 'snapshot.json').exists() else {'skills':[]}
    result['skills'].extend(r for r in old['skills'] if r['repo'] not in result['complete_repos'])
    report = catalog_delta(old, result)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (directory / 'snapshot.json.tmp').write_bytes(raw)
    os.replace(directory / 'snapshot.json.tmp', directory / 'snapshot.json')
    (directory / 'snapshot.sha256').write_text(hashlib.sha256(raw).hexdigest() + '  snapshot.json\n', encoding='utf-8')
    (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'skills':len(result['skills']),'repositories':result['complete_repos'],'errors':result['errors']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
