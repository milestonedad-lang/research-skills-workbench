import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


def record(name="review", body="Review with evidence", sha="a" * 40):
    return {"id": "lab/research/skills/" + name, "name": name,
            "repo": "lab/research", "path": "skills/" + name + "/SKILL.md",
            "commit": sha, "content_hash": hashlib.sha256(body.encode()).hexdigest(),
            "body": body, "description": "Evidence-based literature review",
            "description_zh": "文献综述与证据核验", "discipline": "通用科研",
            "stage": "阅读综述", "license": "MIT", "stars": 15,
            "bundle": {"SKILL.md": "---\nname: " + name + "\ndescription: Review papers\n---\n" + body}}


@pytest.fixture
def client(tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps({"schema_version": 1, "skills": [record()]}, ensure_ascii=False), encoding="utf-8")
    with TestClient(create_app(tmp_path / "data", seed)) as test_client:
        yield test_client


def test_offline_chinese_search_and_combined_filters(client):
    r = client.get("/api/v1/skills", params={"q": "证据", "stage": "阅读综述"})
    assert r.status_code == 200
    assert [s["name"] for s in r.json()["items"]] == ["review"]
    assert client.get("/api/v1/skills?q=不存在").json()["total"] == 0


def test_truthful_statistics_and_duplicate_counts(client):
    duplicate = record("review-copy")
    r = client.post("/api/v1/catalog/import", json={"skills": [record(), duplicate]})
    assert r.status_code == 200
    stats = client.get("/api/v1/stats").json()
    assert (stats["skills"], stats["unique_skills"], stats["repositories"]) == (2, 1, 1)


def test_install_pin_update_and_rollback(client):
    skill_id = record()["id"]
    install = client.post("/api/v1/installations", json={"skill_id": skill_id})
    assert install.status_code == 200
    old = install.json()["version_id"]
    assert client.post("/api/v1/catalog/import", json={"skills": [record(body="New review", sha="b" * 40)]}).status_code == 200
    assert client.get("/api/v1/installations").json()[0]["version_id"] == old
    new = client.get("/api/v1/skills", params={"q": "review"}).json()["items"][0]["version_id"]
    switched = client.post("/api/v1/installations/switch", json={"skill_id": skill_id, "version_id": new})
    assert switched.status_code == 200
    assert client.post("/api/v1/installations/rollback", json={"skill_id": skill_id}).json()["version_id"] == old


def test_failed_install_does_not_change_active_version(client):
    client.post("/api/v1/installations", json={"skill_id": record()["id"]})
    r = client.post("/api/v1/installations/switch", json={"skill_id": record()["id"], "version_id": "nonexistent"})
    assert r.status_code == 404
    assert client.get("/api/v1/installations").json()[0]["commit"] == "a" * 40


def test_rejects_bundle_path_traversal_and_wrong_digest(client):
    bad = record("evil")
    bad["bundle"]["../outside.py"] = "bad"
    assert client.post("/api/v1/catalog/import", json={"skills": [bad]}).status_code == 422
    bad = record("wrong-hash")
    bad["content_hash"] = "0" * 64
    assert client.post("/api/v1/catalog/import", json={"skills": [bad]}).status_code == 422
    assert client.get("/api/v1/stats").json()["skills"] == 1


def test_snapshot_failure_is_atomic(client):
    invalid = record("invalid")
    invalid["commit"] = "branch-name"
    assert client.post("/api/v1/catalog/import", json={"skills": [record("valid"), invalid]}).status_code == 422
    assert client.get("/api/v1/stats").json()["skills"] == 1


def test_missing_model_is_explicit_and_no_fake_run(client):
    project = client.post("/api/v1/projects", json={"name": "研究一"}).json()
    r = client.post("/api/v1/runs", json={"project_id": project["id"], "prompt": "分析", "provider_id": "missing", "budget": 2})
    assert r.status_code == 422
    assert client.get("/api/v1/runs").json() == []


def test_secrets_are_not_returned_by_settings(client):
    config = {"id": "lab", "kind": "openai", "base_url": "https://api.example.org/v1", "model": "example", "api_key": "private-test-key", "input_price": 1, "output_price": 2}
    assert client.post("/api/v1/providers", json=config).status_code == 200
    response = client.get("/api/v1/providers")
    assert "private-test-key" not in response.text
    assert response.json()[0]["has_key"] is True


def test_cross_origin_mutations_rejected(client):
    r = client.post("/api/v1/projects", json={"name": "bad"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_project_files_cannot_escape_directory(client):
    p = client.post("/api/v1/projects", json={"name": "files"}).json()
    r = client.post(f"/api/v1/projects/{p['id']}/files", files={"file": ("../../evil.txt", b"data")})
    assert r.status_code == 422


def test_large_catalog_search_paginates_without_loading_entire_library(client):
    skills = [record(f"skill-{i}", body=f"Body {i}") for i in range(10001)]
    assert client.post("/api/v1/catalog/import", json={"skills": skills}).status_code == 200
    r = client.get("/api/v1/skills", params={"q": "skill-", "limit": 30, "offset": 9990}).json()
    assert r["total"] == 10001
    assert len(r["items"]) == 11
    assert "body" not in r["items"][0]


def test_discovery_does_not_claim_measured_efficiency(client):
    r = client.get("/api/v1/recommendations").json()
    assert r["items"] == []
    assert r["status"] == "待验证"


def test_index_only_entries_are_not_falsely_deduplicated(client):
    items = [record('unknown-a', body=''), record('unknown-b', body='')]
    for item in items:
        item.update(license='UNKNOWN', bundle={}, installable=False)
    client.post('/api/v1/catalog/import', json={'skills':items})
    assert client.get('/api/v1/stats').json()['unique_skills'] == 3


def test_benchmark_cache_is_not_an_active_installed_skill(client):
    client.app.state.store.install(record()['id'], scope='cache')
    assert client.get('/api/v1/skills?installed=true').json()['total'] == 0

