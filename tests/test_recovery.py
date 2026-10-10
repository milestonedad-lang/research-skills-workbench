
import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.core import Store
from tests.test_platform import record


def test_partial_sync_preserves_failed_source_and_old_installed_version(tmp_path):
    store = Store(tmp_path)
    store.import_catalog([record()])
    installed = store.install(record()['id'])
    second = record('second')
    store.import_catalog([second], complete_repos=['unrelated/repo'])
    assert store.search()['total'] == 2
    store.import_catalog([second], complete_repos=['lab/research'])
    assert store.search()['total'] == 1
    assert store.installations()[0]['version_id'] == installed['version_id']
    assert store.version(installed['version_id'])['name'] == 'review'


def test_project_replacement_can_change_skill_and_rollback_old_skill(tmp_path):
    store = Store(tmp_path)
    store.import_catalog([record(),record('alternative',body='Alternate review')])
    first = store.install(record()['id'],scope='project',slot='project:review-task')
    alternate = store.skill(record('alternative')['id'])
    store.install(alternate['id'],alternate['version_id'],scope='project',slot='project:review-task')
    result = store.rollback(alternate['id'],scope='project',slot='project:review-task')
    assert result['version_id'] == first['version_id']
    assert result['skill_id'] == record()['id']


def test_tampered_installed_bundle_is_not_used_for_a_run(tmp_path):
    with TestClient(create_app(tmp_path, tmp_path/'missing.json')) as client:
        client.post('/api/v1/catalog/import',json={'skills':[record()]})
        version = client.post('/api/v1/installations',json={'skill_id':record()['id']}).json()
        (tmp_path/'installed'/version['version_id']/'SKILL.md').write_text('tampered',encoding='utf-8')
        client.post('/api/v1/providers',json={'id':'local','kind':'ollama','model':'test','base_url':'http://127.0.0.1:1'})
        project=client.post('/api/v1/projects',json={'name':'tamper'}).json()
        r=client.post('/api/v1/runs',json={'project_id':project['id'],'provider_id':'local','skill_id':record()['id'],'prompt':'run','budget':0})
        assert r.status_code == 422
        assert client.get('/api/v1/runs').json() == []


def test_binary_resource_is_preserved_in_installed_bundle(tmp_path):
    import base64
    raw=record()
    raw['bundle']['assets/test.bin']=base64.b64encode(b'\x00\xff\x80').decode()
    raw['bundle_encodings']={'assets/test.bin':'base64'}
    store=Store(tmp_path)
    store.import_catalog([raw])
    installation=store.install(raw['id'])
    assert (tmp_path/'installed'/installation['version_id']/'assets/test.bin').read_bytes() == b'\x00\xff\x80'


def test_double_upload_refuses_to_overwrite_original(tmp_path):
    with TestClient(create_app(tmp_path,tmp_path/'missing.json')) as client:
        p=client.post('/api/v1/projects',json={'name':'input'}).json()
        url=f"/api/v1/projects/{p['id']}/files"
        assert client.post(url,files={'file':('data.csv',b'original')}).status_code == 200
        assert client.post(url,files={'file':('data.csv',b'overwritten')}).status_code == 422
        assert (tmp_path/'projects'/p['id']/'inputs'/'data.csv').read_bytes() == b'original'


def test_startup_marks_abandoned_runs_interrupted(tmp_path):
    store=Store(tmp_path)
    store.save('runs',{'id':'old','status':'running'})
    with TestClient(create_app(tmp_path,tmp_path/'missing.json')) as client:
        assert client.get('/api/v1/runs/old').json()['status'] == 'interrupted'


def test_incomplete_bundle_cannot_replace_existing_installation(tmp_path):
    store = Store(tmp_path)
    store.import_catalog([record()])
    installed = store.install(record()['id'])
    incomplete = record(body='Missing required resource', sha='b'*40)
    incomplete.update(installable=False, missing_resources=['assets/large.bin'])
    store.import_catalog([incomplete])
    with pytest.raises(ValueError):
        store.install(incomplete['id'])
    assert store.installations()[0]['version_id'] == installed['version_id']


def test_export_roundtrip_preserves_binary_resources(tmp_path):
    import base64
    import io
    import zipfile
    with TestClient(create_app(tmp_path, tmp_path/'missing.json')) as client:
        raw = record()
        raw['bundle']['assets/test.bin'] = base64.b64encode(b'\x00\xff\x80').decode()
        raw['bundle_encodings'] = {'assets/test.bin':'base64'}
        client.post('/api/v1/catalog/import', json={'skills':[raw]})
        version = client.post('/api/v1/installations', json={'skill_id':raw['id']}).json()['version_id']
        exported = client.get('/api/v1/installations/export/'+version)
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            assert archive.read('review/assets/test.bin') == b'\x00\xff\x80'


def test_repo_commit_without_skill_changes_is_not_reported_as_changed_content(tmp_path):
    store = Store(tmp_path)
    store.import_catalog([record()])
    report = store.import_catalog([record(sha='b'*40)])
    assert report['changed'] == []
    assert report['version_changes'] == [record()['id']]

