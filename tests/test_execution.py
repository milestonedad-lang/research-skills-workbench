import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def model_server():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body['model'] == 'test-model'
            reply = {"model": "test-model-v1", "message": {"content": '{"action":"final","content":"测试报告：平均值为 3。"}'}, "prompt_eval_count": 40, "eval_count": 15}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(reply).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()


def test_provider_transport_produces_artifacts_and_preserves_trace(tmp_path, model_server):
    with TestClient(create_app(tmp_path / 'data', tmp_path / 'missing.json')) as client:
        assert client.post('/api/v1/providers', json={'id':'local','kind':'ollama','base_url':model_server,'model':'test-model'}).status_code == 200
        p = client.post('/api/v1/projects', json={'name':'真实传输集成测试'}).json()
        r = client.post('/api/v1/runs', json={'project_id':p['id'],'provider_id':'local','prompt':'写报告','budget':0,'max_steps':2})
        assert r.status_code == 200
        assert isinstance(r.json(), dict), 'run creation must persist a trace before scheduling'
        identity = r.json()['id']
        for _ in range(100):
            result = client.get('/api/v1/runs/' + identity).json()
            if result['status'] not in {'queued','running'}:
                break
            time.sleep(0.02)
        assert result['status'] == 'completed'
        assert result['actual_model'] == 'test-model-v1'
        assert result['tokens'] == {'input':40,'output':15}
        assert '平均值为 3' in result['output']
        files = client.get(f"/api/v1/projects/{p['id']}/files").json()
        assert any(f['name'].endswith('report.docx') for f in files)
        assert any(f['name'].endswith('report.md') for f in files)
        assert result['events'][0]['type'] == 'started'


def test_paid_execution_requires_prices_before_start(tmp_path):
    with TestClient(create_app(tmp_path, tmp_path / 'missing.json')) as client:
        client.post('/api/v1/providers', json={'id':'paid','kind':'openai','base_url':'https://example.org/v1','model':'test','api_key':'test-secret'})
        p = client.post('/api/v1/projects', json={'name':'budget'}).json()
        r = client.post('/api/v1/runs', json={'project_id':p['id'],'provider_id':'paid','prompt':'run','budget':2})
        assert r.status_code == 422
        assert client.get('/api/v1/runs').json() == []


def test_benchmark_has_no_skill_baseline_and_frozen_versions(tmp_path, model_server):
    with TestClient(create_app(tmp_path, tmp_path / 'missing.json')) as client:
        client.post('/api/v1/providers', json={'id':'local','kind':'ollama','base_url':model_server,'model':'test-model'})
        b = client.post('/api/v1/benchmarks', json={'template':'writing','provider_id':'local','version_ids':[],'budget':0,'repetitions':3})
        assert b.status_code == 200
        assert b.json()['candidates'][0]['version_id'] is None
        assert b.json()['repetitions'] == 3
        identity = b.json()['id']
        for _ in range(200):
            result = client.get('/api/v1/benchmarks/' + identity).json()
            if result['status'] not in {'queued','running'}:
                break
            time.sleep(0.02)
        assert result['status'] == 'completed'
        assert len(result['results']) == 3
        # Writing needs anonymous human review; automatic output alone cannot win.
        assert result['ranking'][0]['eligible'] is False
        assert client.get('/api/v1/recommendations').json()['items'] == []

