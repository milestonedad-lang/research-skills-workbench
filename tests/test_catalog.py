import io
import zipfile

import pytest


def archive(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, content in entries.items():
            z.writestr('repo-head/' + name, content)
    return buf.getvalue()


def test_scanner_preserves_relative_resources_and_license():
    from server.catalog import parse_archive
    raw = archive({'LICENSE':'MIT License', 'skills/analysis/SKILL.md':'---\nname: analysis\ndescription: Analyze data\n---\nRead references/method.md', 'skills/analysis/references/method.md':'Method A', 'skills/analysis/scripts/run.py':'print(3)'})
    items = parse_archive(raw, 'lab/research', 'a'*40, 'MIT', 10)
    assert len(items) == 1
    assert items[0]['bundle']['references/method.md'] == 'Method A'
    assert items[0]['bundle']['scripts/run.py'] == 'print(3)'
    assert items[0]['commit'] == 'a'*40


def test_unknown_license_is_index_only():
    from server.catalog import parse_archive
    raw = archive({'skills/foo/SKILL.md':'---\nname: foo\ndescription: Analyze data\n---\nPrivate workflow'})
    items = parse_archive(raw, 'lab/private', 'a'*40, 'UNKNOWN', 0)
    assert items[0]['bundle'] == {}
    assert items[0]['body'] == ''
    assert items[0]['installable'] is False


def test_zip_traversal_is_rejected_before_extraction():
    from server.catalog import parse_archive
    raw = archive({'skills/foo/SKILL.md':'---\nname: foo\ndescription: x\n---\nx', 'skills/foo/../../escape.py':'bad'})
    with pytest.raises(ValueError):
        parse_archive(raw, 'lab/research', 'a'*40, 'MIT', 0)


def test_oversize_resource_cannot_create_an_installable_partial_package():
    from server.catalog import parse_archive
    raw = archive({'LICENSE':'MIT License', 'skills/foo/SKILL.md':'---\nname: foo\ndescription: x\n---\nUse assets/large.bin', 'skills/foo/assets/large.bin':b'x' * 2_000_001})
    item = parse_archive(raw, 'lab/research', 'a'*40, 'MIT', 0)[0]
    assert item['installable'] is False
    assert item['missing_resources'] == ['assets/large.bin']


def test_failed_sync_is_recorded_and_not_retried_at_every_startup(tmp_path):
    import asyncio
    from unittest.mock import patch

    from server.catalog import startup_sync, sync_catalog
    from server.core import Store
    store = Store(tmp_path)
    store.save('settings', {'id':'main', 'snapshot_repo':'lab/empty'})
    with patch('server.catalog.httpx.Client.get', side_effect=ValueError('rate limited')):
        assert sync_catalog(store, [])['status'] == 'failed'
        asyncio.run(startup_sync(store))
    assert len(store.list('updates')) == 1


def test_public_monthly_report_separates_commit_reference_from_content_change():
    from scripts.scan_catalog import catalog_delta
    old = {'skills':[{'id':'same','repo':'a/b','commit':'a','body':'x','bundle':{'x':'y'},'license':'MIT'}, {'id':'gone','repo':'a/b','body':'old'}]}
    new = {'skills':[{'id':'same','repo':'a/b','commit':'b','body':'x','bundle':{'x':'y'},'license':'MIT'}, {'id':'new','repo':'a/b','body':'new'}], 'errors':[]}
    report = catalog_delta(old,new)
    assert report['added'] == ['new']
    assert report['removed'] == ['gone']
    assert report['changed'] == []
    assert report['version_changes'] == ['same']

