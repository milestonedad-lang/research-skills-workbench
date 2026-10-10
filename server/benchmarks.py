"""Fixed-input comparisons. Qualitative writing requires anonymous human scoring."""
import asyncio
import json
import re

from server.core import digest, now, rank_results, safe_path, uid
from server.execution import execute_run, prepare_run
from server.providers import load_provider, prices

TEMPLATES = {
    "literature": {"id":"literature", "name":"文献与引用", "prompt":"核验 DOI 10.1038/nature14539，列出标题、发表年与来源，不凭记忆补充。必须调用 crossref_doi 工具。", "requires_docker":False},
    "analysis": {"id":"analysis", "name":"数据分析", "prompt":"实际读取 /inputs/sample.csv 并执行 Python。计算 value 的平均值、样本标准差与有效样本数，保存 result.json（键 mean、std、n），报告处理缺失值的方法。", "requires_docker":True},
    "plot": {"id":"plot", "name":"统计绘图", "prompt":"实际读取 /inputs/sample.csv，运行 Python 生成 value 分布图，保存 figure.png 和绘图脚本。横轴 value，纵轴 count。", "requires_docker":True},
    "writing": {"id":"writing", "name":"科研写作", "prompt":"依据给定事实写一段中文结果及局限：某探索研究样本 n=5，均值 3，没有对照组，不能做因果推断。不得添加 p 值、引用或未测指标。", "requires_docker":False},
}


def prepare_benchmark(store, payload):
    template = TEMPLATES.get(payload.get("template"))
    if not template:
        raise ValueError("请选择有效基准")
    provider_ids = payload.get("provider_ids") or [payload["provider_id"]]
    versions = payload.get("version_ids", [])
    mode = payload.get("mode", "skills")
    if mode == "models" and len(versions) != 1:
        raise ValueError("比较模型时需固定一个技能版本")
    if mode == "skills" and len(provider_ids) != 1:
        raise ValueError("比较技能时需固定一个模型")
    candidates = []
    if mode == "models":
        candidates = [{"candidate": "model:" + p, "provider_id":p, "version_id":versions[0]} for p in provider_ids]
    else:
        candidates = [{"candidate":"baseline", "provider_id":provider_ids[0], "version_id":None}]
        candidates.extend({"candidate":v, "provider_id":provider_ids[0], "version_id":v} for v in dict.fromkeys(versions))
    if len(candidates) > 6:
        raise ValueError("单次最多比较 6 个候选")
    for item in candidates:
        p = load_provider(store, item["provider_id"])
        prices(p)
        if item["version_id"]:
            v = store.version(item["version_id"])
            store.install(v["id"], v["version_id"], scope="cache")
    budget = float(payload.get("budget", 0))
    if any(load_provider(store, p)["kind"] != "ollama" for p in provider_ids) and budget <= 0:
        raise ValueError("付费比较必须设置正数预算")
    if template["requires_docker"]:
        import shutil
        if not shutil.which("docker"):
            raise ValueError("此基准需要 Docker 执行代码，请先完成配置")
    identity, project_id = uid(), uid()
    try:
        settings = store.get('settings', 'main')
    except KeyError:
        settings = {}
    if template['requires_docker']:
        import subprocess
        image = settings.get('runner_image', 'research-workbench-runner:0.1.0')
        inspected = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], capture_output=True, timeout=20)
        if inspected.returncode:
            raise ValueError('请先构建科研 runner 镜像')
        settings['runner_digest'] = inspected.stdout.decode().strip()
    # Keep encrypted keys private; freeze before the batch is queued.
    store.save('benchmark-configs', {'id':identity, 'providers':{p:store.get('providers', p) for p in provider_ids}, 'settings':settings})
    directory = store.root / "projects" / project_id / "inputs"
    directory.mkdir(parents=True)
    (directory / "sample.csv").write_text("value\n1\n2\n3\n4\n5\n\n", encoding="utf-8")
    store.save("projects", {"id":project_id, "name":"基准 · " + template["name"], "created_at":now(), "benchmark":True})
    store.create_budget(identity, budget)
    r = {"id":identity, "project_id":project_id, "template":template["id"], "mode":mode, "candidates":candidates,
         "repetitions":min(max(int(payload.get("repetitions", 3)), 1), 5), "status":"queued", "results":[], "ranking":[], "created_at":now(),
         "context":{"prompt":template["prompt"], "temperature":0, "max_steps":12, "max_output":2048,
                    "template_revision":"1", "data_hash":digest((directory / "sample.csv").read_text()),
                    "runner_digest":settings.get('runner_digest'),
                    "providers":[{k:v for k,v in store.get("providers", p).items() if k != 'api_key'} for p in provider_ids]}}
    return store.save("benchmarks", r)


def grade(store, run, template):
    directory = store.root / "projects" / run["project_id"] / "runs" / run["id"] / "outputs"
    if run["status"] != "completed":
        return 0, "运行未完成"
    if template == "writing":
        return 0, "待匿名人工评分"
    if template == "literature":
        for event in run["events"]:
            if event.get("action") == "crossref_doi":
                records = event.get("result", {}).get("records", [])
                for item in records:
                    output = run.get("output", "").lower()
                    title = (item.get("title") or [""])[0].lower()
                    parts = item.get("published", {}).get("date-parts", [[]])[0]
                    if item.get("DOI", "").lower() == "10.1038/nature14539" and title and title in output and parts and str(parts[0]) in output and "14539" in output:
                        return 1, "DOI、标题、发表年与工具元数据一致；语义质量仍需人工复核"
        return 0, "未取得对应 DOI 的工具证据"
    if template == "analysis":
        try:
            import math
            r = json.loads((directory / "result.json").read_text())
            executed = any(e.get('action') == 'python' and e.get('result',{}).get('exit_code') == 0 for e in run['events'])
            passed = executed and math.isclose(float(r['mean']), 3, abs_tol=1e-6) and math.isclose(float(r['std']), 1.58113883, abs_tol=1e-6) and r['n'] == 5
            return int(passed), "数值核验" if passed else "均值、样本标准差或样本数不正确"
        except (OSError, ValueError, KeyError, TypeError):
            return 0, "缺少可核验 result.json"
    if template == "plot":
        path = directory / 'figure.png'
        ok = path.exists() and path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') and any(e.get('action') == 'python' and e.get('result',{}).get('exit_code') == 0 for e in run['events'])
        return int(ok), "PNG 与成功执行记录核验；图意和标注需人工复核"
    return 0, "未知基准"


async def execute_benchmark(store, identity):
    b = store.get("benchmarks", identity)
    b["status"] = "running"
    store.save("benchmarks", b)
    try:
        # Freeze all run inputs/provider configs before the first model request.
        prepared = []
        frozen = store.get('benchmark-configs', identity)
        for item in b["candidates"]:
            for repetition in range(b["repetitions"]):
                r = prepare_run(store, {"project_id":b["project_id"], "provider_id":item["provider_id"], "version_id":item["version_id"],
                                       "prompt":b["context"]["prompt"], "budget":store.budget(identity)["cap"], "benchmark_id":identity,
                                       "max_steps":12, "max_output":2048, "temperature":0}, identity,
                                frozen['providers'][item['provider_id']], frozen['settings'])
                prepared.append((item, repetition, r))
        for item, repetition, r in prepared:
            if store.budget(identity)["spent"] >= store.budget(identity)["cap"] and store.budget(identity)["cap"] > 0:
                b["status"] = "budget_exhausted"
                break
            run = await execute_run(store, r["id"])
            if run['status'] == 'cancelled':
                raise asyncio.CancelledError()
            quality, check = grade(store, run, b["template"])
            result = {"run_id":run["id"], "candidate":item["candidate"], "repetition":repetition, "status":run["status"],
                      "quality":0 if b['template']=='plot' else quality, "auto_quality":quality,
                      "check":check, "duration":run["duration"], "cost":run["cost"], "tokens":run["tokens"], "error":run.get("error")}
            b["results"].append(result)
            b["ranking"] = rank_results(b["results"])
            store.save("benchmarks", b)
            if run['status'] == 'budget_exhausted':
                b['status'] = 'budget_exhausted'
                break
        else:
            b["status"] = "completed"
    except asyncio.CancelledError:
        b["status"] = "cancelled"
    except Exception as exc:
        b.update(status="failed", error=str(exc)[:400])
    finally:
        # Pending trials are retained explicitly and never counted as successes.
        for r in store.list('runs'):
            if r.get('benchmark_id') == identity and r['status'] == 'queued':
                r.update(status='not_run', error='比较已停止，未发起模型请求')
                store.save('runs', r)
        b.update(finished_at=now(), budget=store.budget(identity))
        store.save("benchmarks", b)


def blind_outputs(store, identity):
    b = store.get('benchmarks', identity)
    result = []
    mapping = []
    for index, row in enumerate(sorted(b['results'], key=lambda r: digest(r['run_id']))):
        label = '样本 ' + str(index + 1)
        mapping.append({'label':label, 'run_id':row['run_id']})
        run = store.get('runs', row['run_id'])
        images = [a for a in run.get('artifacts', []) if a['name'].lower().endswith('.png')]
        result.append({'label':label, 'output':run.get('output',''), 'score':row.get('human_score'),
                       'images':[f'/api/v1/benchmarks/{identity}/blind/{index}/image/{n}' for n in range(len(images))]})
    store.save('blind-maps', {'id':identity, 'items':mapping})
    return result


def blind_image(store, identity, sample, image):
    rows = sorted(store.get('benchmarks', identity)['results'], key=lambda r:digest(r['run_id']))
    if not 0 <= sample < len(rows):
        raise ValueError('匿名样本不存在')
    run = store.get('runs', rows[sample]['run_id'])
    images = [a for a in run.get('artifacts', []) if a['name'].lower().endswith('.png')]
    if not 0 <= image < len(images):
        raise ValueError('图片不存在')
    path = safe_path(store.root/'projects'/run['project_id'], images[image]['name'])
    with path.open('rb') as file:
        if file.read(8) != b'\x89PNG\r\n\x1a\n':
            raise ValueError('不是可预览的 PNG')
    return path


def score_output(store, identity, payload):
    mapping = store.get('blind-maps', identity)
    run_id = next((r['run_id'] for r in mapping['items'] if r['label'] == payload.get('label')), None)
    if not run_id:
        raise ValueError('评分样本不存在')
    score = int(payload.get('score', -1))
    if not 0 <= score <= 5:
        raise ValueError('人工评分为 0—5 分')
    b = store.get('benchmarks', identity)
    for row in b['results']:
        if row['run_id'] == run_id:
            row.update(human_score=score, human_note=payload.get('note',''), reviewed_at=now())
            if b['template'] == 'writing':
                output = store.get('runs', run_id).get('output','')
                facts = '3' in output and '5' in output and ('因果' in output or '对照' in output)
                row['quality'] = 1 if score >= 4 and facts and not re.search(r'p\s*[=<]\s*0\.\d', output, re.I) else 0
                row['check'] = '人工评分及事实约束核验'
            if b['template'] == 'plot':
                row['quality'] = 1 if row.get('auto_quality') == 1 and score >= 4 else 0
                row['check'] = 'PNG、实际执行与人工图意检查'
    b['ranking'] = rank_results(b['results'])
    return store.save('benchmarks', b)
