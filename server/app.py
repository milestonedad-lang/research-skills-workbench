"""Loopback API and static production UI."""
import asyncio
import json
import os
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from server.core import DISCIPLINES, STAGES, Store, now, safe_path, uid

ROOT = Path(__file__).resolve().parents[1]


def create_app(data_dir=None, seed_path=None):
    store = Store(data_dir or os.environ.get("WORKBENCH_DATA", ROOT / "data"))
    seed = Path(seed_path or ROOT / "catalog" / "snapshot.json")
    if seed.exists() and not store.search(limit=1)["total"]:
        store.import_catalog(json.loads(seed.read_text(encoding="utf-8"))["skills"])
    jobs = {}

    @asynccontextmanager
    async def lifespan(app):
        # Interrupted jobs are never silently labelled successful on restart.
        for kind in ("runs", "benchmarks"):
            for row in store.list(kind):
                if row.get("status") in {"queued", "running"}:
                    row.update(status="interrupted", error="服务重启，运行已中断", finished_at=now())
                    store.save(kind, row)
        from server.catalog import startup_sync
        background = asyncio.create_task(startup_sync(store))
        yield
        background.cancel()
        for job in list(jobs.values()):
            job.cancel()
        await asyncio.gather(background, *jobs.values(), return_exceptions=True)

    app = FastAPI(title="科研技能工作台", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.jobs = store, jobs

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        allowed = {"127.0.0.1", "localhost", "::1", "testserver"}
        if request.url.hostname not in allowed:
            return JSONResponse({"detail": "仅允许本机访问"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and (urlparse(origin).hostname not in allowed or urlparse(origin).scheme not in {"http", "https"}):
            return JSONResponse({"detail": "不允许跨站访问本地科研数据"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "记录不存在"}, status_code=404)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/v1/stats")
    def stats():
        with store.connect() as c:
            skills, repos = c.execute("SELECT COUNT(*),COUNT(DISTINCT repo) FROM skills WHERE active=1").fetchone()
            unique = c.execute("SELECT COUNT(DISTINCT CASE WHEN v.body='' THEN s.id ELSE json_extract(v.record,'$.content_hash') END) FROM skills s JOIN versions v ON v.id=s.version_id WHERE active=1").fetchone()[0]
        runs = store.list("runs")
        return {"skills": skills, "repositories": repos, "unique_skills": unique, "installed": len([i for i in store.installations() if i['scope'] != 'cache']),
                "runs": len(runs), "running": sum(r.get("status") in {"queued", "running"} for r in runs),
                "measured": len({r.get("skill_id") for r in runs if r.get("benchmark_id") and r.get("status") == "completed"})}

    @app.get("/api/v1/taxonomy")
    def taxonomy():
        return {"disciplines": DISCIPLINES, "stages": STAGES}

    @app.get("/api/v1/skills")
    def skills(q: str = "", discipline: str = "", stage: str = "", installed: bool = False,
               measured: bool = False, sort: str = "stars", limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.search(q, discipline, stage, installed, limit, offset, sort, measured)

    @app.get("/api/v1/skill")
    def detail(id: str):
        return store.skill(id)

    @app.get("/api/v1/version/{identity}")
    def version(identity: str):
        return store.version(identity)

    @app.post("/api/v1/catalog/import")
    def import_catalog(payload: dict):
        return store.import_catalog(payload["skills"], payload.get("complete_repos", []))

    @app.post("/api/v1/catalog/import-file")
    async def import_file(file: UploadFile = File(...)):
        raw = await file.read(50_000_001)
        if len(raw) > 50_000_000:
            raise ValueError("导入文件超过 50MB")
        payload = json.loads(raw)
        return store.import_catalog(payload["skills"])

    @app.post("/api/v1/catalog/local")
    async def import_local(file: UploadFile = File(...)):
        from server.catalog import import_local_bundle
        return import_local_bundle(store, await file.read(20_000_001))

    @app.get("/api/v1/sources")
    def sources():
        custom = store.list("sources")
        defaults = json.loads((ROOT / "catalog" / "sources.json").read_text(encoding="utf-8")) if (ROOT / "catalog" / "sources.json").exists() else []
        return list({r["repo"]: r for r in [*defaults, *custom]}.values())

    @app.post("/api/v1/sources")
    def add_source(payload: dict):
        repo = payload.get("repo", "").removeprefix("https://github.com/").removesuffix(".git").strip("/")
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise ValueError("请输入 owner/repo 或 GitHub 仓库地址")
        return store.save("sources", {"id": repo, "repo": repo, "license": "UNKNOWN", "branch": payload.get("branch", "main")})

    @app.get("/api/v1/updates")
    def updates():
        return store.list("updates")

    @app.post("/api/v1/sync")
    async def sync(payload: dict):
        from server.catalog import sync_catalog
        return await asyncio.to_thread(sync_catalog, store, sources(), bool(payload.get("scan", False)))

    @app.get("/api/v1/installations")
    def installations():
        return store.installations()

    @app.post("/api/v1/installations")
    @app.post("/api/v1/installations/switch")
    def install(payload: dict):
        return store.install(payload["skill_id"], payload.get("version_id"), payload.get("scope", "global"), payload.get("slot"), payload.get('expected'))

    @app.post("/api/v1/installations/rollback")
    def rollback(payload: dict):
        return store.rollback(payload["skill_id"], payload.get("scope", "global"), payload.get("slot"))

    @app.get("/api/v1/installations/export/{identity}")
    def export_skill(identity: str):
        import base64
        import zipfile
        r = store.version(identity)
        output = store.root / "exports" / (identity + ".zip")
        output.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in r.get("bundle", {}).items():
                data = base64.b64decode(content, validate=True) if r.get('bundle_encodings', {}).get(name) == 'base64' else content.encode('utf-8')
                archive.writestr(r["name"] + "/" + name, data)
        return FileResponse(output, filename=r["name"] + ".zip")

    @app.get("/api/v1/projects")
    def projects():
        return store.list("projects")

    @app.post("/api/v1/projects")
    def project(payload: dict):
        name = payload.get("name", "").strip()
        if not name or len(name) > 200:
            raise ValueError("请输入有效项目名称")
        p = {"id": uid(), "name": name, "created_at": now(), "notes": payload.get("notes", "")}
        (store.root / "projects" / p["id"] / "inputs").mkdir(parents=True)
        return store.save("projects", p)

    @app.get("/api/v1/projects/{identity}/files")
    def project_files(identity: str):
        store.get("projects", identity)
        root = store.root / "projects" / identity
        return [{"name": str(p.relative_to(root)).replace("\\", "/"), "size": p.stat().st_size}
                for p in root.rglob("*") if p.is_file()]

    @app.post("/api/v1/projects/{identity}/files")
    async def upload(identity: str, file: UploadFile = File(...)):
        store.get("projects", identity)
        name = file.filename or "file"
        if "/" in name or "\\" in name:
            raise ValueError("请仅上传文件名，不包含目录")
        path = safe_path(store.root / "projects" / identity / "inputs", name)
        raw = await file.read(50_000_001)
        if len(raw) > 50_000_000:
            raise ValueError("文件超过 50MB")
        try:
            with path.open("xb") as out:
                out.write(raw)
        except FileExistsError:
            raise ValueError("同名原始文件已存在，请改名后上传") from None
        return {"name": name, "size": len(raw)}

    @app.get("/api/v1/projects/{identity}/download")
    def download(identity: str, path: str):
        store.get("projects", identity)
        resolved = safe_path(store.root / "projects" / identity, path)
        if not resolved.is_file():
            raise HTTPException(404, "文件不存在")
        return FileResponse(resolved, filename=resolved.name, media_type="application/octet-stream")

    @app.get("/api/v1/providers")
    def providers():
        return [{**{k: v for k, v in p.items() if k != "api_key"}, "has_key": bool(p.get("api_key"))} for p in store.list("providers")]

    @app.post("/api/v1/providers")
    def provider(payload: dict):
        from server.providers import save_provider
        return save_provider(store, payload)

    @app.post("/api/v1/providers/{identity}/test")
    async def provider_test(identity: str):
        from server.providers import list_models
        return await list_models(store, identity)

    @app.get("/api/v1/settings")
    def settings():
        try:
            config = store.get("settings", "main")
        except KeyError:
            config = {"id": "main", "display_name": "科研技能工作台", "snapshot_repo": "", "runner_image": "research-workbench-runner:0.1.0"}
        return {**config, "docker_available": shutil.which("docker") is not None,
                "data_dir": str(store.root), "setup_required": not providers()}

    @app.post("/api/v1/settings")
    def save_settings(payload: dict):
        config = {k: payload[k] for k in ("display_name", "snapshot_repo", "runner_image") if k in payload}
        config["id"] = "main"
        if config.get("snapshot_repo") and not re.fullmatch(r"[\w.-]+/[\w.-]+", config["snapshot_repo"]):
            raise ValueError("快照仓库必须为 owner/repo")
        if config.get("runner_image") and not re.fullmatch(r"[\w./:@-]+", config["runner_image"]):
            raise ValueError("执行镜像名称无效")
        return store.save("settings", {**settings(), **config})

    @app.get("/api/v1/runs")
    def runs():
        return store.list("runs")

    @app.get("/api/v1/runs/{identity}")
    def run_detail(identity: str):
        return store.get("runs", identity)

    @app.post("/api/v1/runs")
    async def run(payload: dict):
        from server.execution import execute_run, prepare_run
        r = prepare_run(store, payload)
        jobs[r["id"]] = asyncio.create_task(execute_run(store, r["id"]))
        return r

    @app.post("/api/v1/runs/{identity}/cancel")
    async def cancel(identity: str):
        r = store.get("runs", identity)
        if r["status"] in {"queued", "running"}:
            r["cancel_requested"] = True
            store.save("runs", r)
            if identity in jobs:
                jobs[identity].cancel()
                await asyncio.gather(jobs[identity], return_exceptions=True)
        return store.get("runs", identity)

    @app.get("/api/v1/runs/{identity}/events")
    async def events(identity: str, request: Request):
        store.get("runs", identity)
        async def stream():
            prior = None
            while not await request.is_disconnected():
                r = store.get("runs", identity)
                serialized = json.dumps(r, ensure_ascii=False)
                if serialized != prior:
                    yield "data: " + serialized + "\n\n"
                    prior = serialized
                if r["status"] not in {"queued", "running"}:
                    break
                await asyncio.sleep(0.5)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/api/v1/benchmarks/templates")
    def templates():
        from server.benchmarks import TEMPLATES
        return list(TEMPLATES.values())

    @app.get("/api/v1/benchmarks")
    def benchmarks():
        return store.list("benchmarks")

    @app.post("/api/v1/benchmarks")
    async def benchmark(payload: dict):
        from server.benchmarks import execute_benchmark, prepare_benchmark
        b = prepare_benchmark(store, payload)
        jobs[b["id"]] = asyncio.create_task(execute_benchmark(store, b["id"]))
        return b

    @app.post("/api/v1/benchmarks/{identity}/cancel")
    async def cancel_benchmark(identity: str):
        b = store.get("benchmarks", identity)
        if identity in jobs:
            jobs[identity].cancel()
            await asyncio.gather(jobs[identity], return_exceptions=True)
        return store.get("benchmarks", b["id"])

    @app.get("/api/v1/benchmarks/{identity}")
    def benchmark_detail(identity: str):
        return store.get("benchmarks", identity)

    @app.get("/api/v1/benchmarks/{identity}/blind")
    def blind(identity: str):
        from server.benchmarks import blind_outputs
        return blind_outputs(store, identity)

    @app.post("/api/v1/benchmarks/{identity}/score")
    def score(identity: str, payload: dict):
        from server.benchmarks import score_output
        return score_output(store, identity, payload)

    @app.get('/api/v1/benchmarks/{identity}/blind/{sample}/image/{image}')
    def preview(identity: str, sample: int, image: int):
        from server.benchmarks import blind_image
        return FileResponse(blind_image(store, identity, sample, image), media_type='image/png')

    @app.get("/api/v1/recommendations")
    def recommendations():
        items = []
        for b in store.list("benchmarks"):
            eligible = [r for r in b.get("ranking", []) if r["eligible"] and r["samples"] >= 3]
            if b.get("status") == "completed" and eligible and len(b.get('candidates', [])) >= 2 and eligible[0]['candidate'] != 'baseline':
                items.append({"benchmark_id": b["id"], "template": b["template"], "context": b["context"], "result": eligible[0], "candidates": b["candidates"]})
        return {"status": "有实测证据" if items else "待验证", "items": items}

    @app.post("/api/v1/catalog/translate")
    async def translate(payload: dict):
        from server.execution import translate_skills
        return await translate_skills(store, payload)

    web = ROOT / "web" / "dist"
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app

