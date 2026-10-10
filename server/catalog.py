"""Public-source collection; no LLM calls and no execution of upstream code."""
import asyncio
import base64
import io
import re
import zipfile
from pathlib import PurePosixPath

import httpx
import yaml

from server.core import digest, now, safe_path, uid

PERMITTED = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "CC0-1.0"}
ZH = {
    "literature-review": ("文献检索、筛选与证据可追溯的综述写作", "通用科研", "阅读综述"),
    "scientific-writing": ("根据证据整理科研论文结构与正文", "通用科研", "写作"),
    "scientific-visualization": ("生成可复现的科研图表与出版用图片", "通用科研", "绘图"),
    "statistical-analysis": ("统计方法选择、假设检查与结果报告", "数学统计", "数据分析"),
    "scientific-critical-thinking": ("审视研究设计、证据强度与推断边界", "通用科研", "研究设计"),
    "scientific-brainstorming": ("围绕研究问题讨论候选假设与验证方向", "通用科研", "研究设计"),
    "peer-review": ("检查论文方法、结果、引用及结论的一致性", "通用科研", "投稿准备"),
    "research-grants": ("科研项目申请的结构、论证与材料组织", "通用科研", "写作"),
    "scikit-learn": ("机器学习建模、验证与模型比较", "计算机与 AI", "数据分析"),
    "pytorch-lightning": ("深度学习训练、实验记录与模型评估", "计算机与 AI", "数据分析"),
    "geopandas": ("地理空间数据处理、空间分析与地图绘制", "地球环境", "数据分析"),
    "sympy": ("符号数学、公式推导与代数计算", "数学统计", "数据分析"),
    "statsmodels": ("统计回归、模型诊断与时间序列分析", "数学统计", "数据分析"),
    "matplotlib": ("用代码绘制并导出科研图表", "通用科研", "绘图"),
    "seaborn": ("统计数据探索与可视化", "数学统计", "绘图"),
    "plotly": ("交互式数据图表与可视化", "通用科研", "绘图"),
    "scientific-slides": ("整理科研汇报、学术幻灯片与讲述结构", "通用科研", "写作"),
    "biorxiv-database": ("检索生物医学预印本并记录来源", "生物医学", "检索"),
    "pubmed-database": ("检索 PubMed 文献与书目信息", "生物医学", "检索"),
    "rdkit": ("分子结构处理、化学信息计算与分析", "化学材料", "数据分析"),
    "astropy": ("天文数据、单位与坐标计算", "物理天文", "数据分析"),
    "pymatgen": ("材料结构与性质计算", "化学材料", "数据分析"),
    "fred-economic-data": ("检索与分析 FRED 经济时间序列", "经济金融", "检索"),
    "qutip": ("量子系统建模与数值计算", "物理天文", "数据分析"),
    "scanpy": ("单细胞转录组数据分析与质量检查", "生物医学", "数据分析"),
    "document-skills": ("文档生成与编辑工作流", "通用科研", "写作"),
}


def classify(name, description):
    if name in ZH:
        return ZH[name]
    text = (name + " " + description).lower()
    discipline = "通用科研"
    for label, words in [("生物医学", "bio genom clinical medical protein gene cell drug"), ("化学材料", "chemical chemistry molecular materials crystal"),
                         ("物理天文", "physics quantum astronomy"), ("地球环境", "geo climate earth satellite ocean"),
                         ("经济金融", "financial economic trading treasury"), ("管理与社会科学", "social qualitative survey management"),
                         ("计算机与 AI", "machine learning neural model training"), ("数学统计", "statistic math regression bayesian"),
                         ("工程技术", "engineering simulation cad fluid battery")]:
        if any(w in text for w in words.split()):
            discipline = label
            break
    stage = "研究设计"
    for label, words in [("绘图", "plot visualization figure"), ("阅读综述", "review literature synthesis"), ("引用核验", "citation reference check"),
                         ("检索", "search database lookup"), ("写作", "writing document grant"), ("投稿准备", "submission journal"),
                         ("数据分析", "analysis statistics data processing")]:
        if any(w in text for w in words.split()):
            stage = label
            break
    return "", discipline, stage


def detect_license(text):
    if "MIT License" in text or "Permission is hereby granted, free of charge" in text:
        return "MIT"
    if "Apache License" in text and "Version 2.0" in text:
        return "Apache-2.0"
    if "CC0" in text:
        return "CC0-1.0"
    return "UNKNOWN"


def parse_archive(raw, repo, commit, license_name, stars):
    if len(raw) > 600_000_000:
        raise ValueError("仓库归档超过 600MB")
    records = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files = {}
        if sum(i.file_size for i in z.infolist()) > 1_500_000_000:
            raise ValueError("仓库解压总量超出限制")
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = info.filename.split("/", 1)[-1]
            safe_path(".", rel)
            # ZIP symlinks are never followed or installed.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("归档包含符号链接")
            files[rel] = info
        root_license = next((z.read(i).decode("utf-8", errors="replace") for path, i in files.items() if path.lower() in {"license", "license.md", "license.txt"}), "")
        detected_root = detect_license(root_license)
        for path, info in files.items():
            if PurePosixPath(path).name != "SKILL.md" or info.file_size > 2_000_000:
                continue
            text = z.read(info).decode("utf-8", errors="replace")
            parts = text.split("---", 2)
            if len(parts) != 3 or parts[0].strip():
                continue
            metadata = yaml.safe_load(parts[1])
            if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str) or not metadata.get("description"):
                continue
            prefix = str(PurePosixPath(path).parent)
            prefix = "" if prefix == "." else prefix + "/"
            skill_license = detected_root if detected_root != "UNKNOWN" else license_name
            declared = metadata.get("license", "")
            if declared:
                skill_license = declared if declared in PERMITTED else "UNKNOWN"
            local_license = next((z.read(i).decode("utf-8", errors="replace") for p, i in files.items() if p.startswith(prefix) and p[len(prefix):].lower() in {"license", "license.md", "license.txt"}), "")
            if local_license:
                skill_license = detect_license(local_license)
            allowed = skill_license in PERMITTED
            missing_resources = [p[len(prefix):] for p, item in files.items() if p.startswith(prefix) and item.file_size > 2_000_000]
            bundle, encodings = {}, {}
            if allowed:
                for p, item in files.items():
                    if p.startswith(prefix) and item.file_size <= 2_000_000:
                        local_name = p[len(prefix):]
                        if not local_name:
                            continue
                        content = z.read(item)
                        try:
                            bundle[local_name] = content.decode("utf-8")
                        except UnicodeDecodeError:
                            bundle[local_name] = base64.b64encode(content).decode()
                            encodings[local_name] = "base64"
                if root_license:
                    bundle["UPSTREAM_LICENSE.txt"] = root_license
            description = str(metadata["description"])
            zh, discipline, stage = classify(metadata["name"], description)
            body = parts[2].strip() if allowed else ""
            records.append({"id": repo + "/" + path.removesuffix("/SKILL.md"), "repo": repo, "path": path, "name": metadata["name"],
                            "description": description, "description_zh": zh, "translation_status": "已整理" if zh else "待中文整理",
                            "classification_status": "人工整理" if zh else "规则分类，待复核", "discipline": discipline, "stage": stage,
                            "commit": commit, "content_hash": digest(body), "body": body, "bundle": bundle, "bundle_encodings": encodings,
                            "stars": stars or 0, "stars_known": stars is not None, "license": skill_license,
                            "installable": allowed and not missing_resources, "missing_resources":missing_resources,
                            "compatibility": metadata.get("compatibility", "请核查正文与 scripts 依赖"), "fetched_at": now(),
                            "source_url": f"https://github.com/{repo}/blob/{commit}/{path}",
                            "tutorial": "阅读用途、许可证和依赖 → 安装固定版本 → 在科研项目选择技能与模型 → 用公开样例验证输出 → 根据实测决定保留或替换。"})
    return records


def scan_sources(sources):
    records, successes, errors = [], [], []
    with httpx.Client(timeout=90, follow_redirects=True, headers={"User-Agent": "research-skills-workbench/0.1"}) as client:
        for source in sources:
            repo = source["repo"]
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
                errors.append({"repo": repo, "error": "仓库名称无效"})
                continue
            try:
                page = client.get("https://github.com/" + repo)
                page.raise_for_status()
                match = re.search(r'"currentOid":"([0-9a-f]{40})"', page.text)
                if not match:
                    raise ValueError("未取得固定提交 SHA，保留旧记录")
                sha = match[1]
                stars_match = re.search(r'"stargazerCount":(\d+)', page.text)
                stars = int(stars_match[1]) if stars_match else None
                response = client.get(f"https://codeload.github.com/{repo}/zip/{sha}")
                response.raise_for_status()
                imported = parse_archive(response.content, repo, sha, source.get("license", "UNKNOWN"), stars)
                if not imported:
                    raise ValueError("没有有效 SKILL.md；目录列表需添加其中的真实仓库")
                records.extend(imported)
                successes.append(repo)
            except (httpx.HTTPError, ValueError, zipfile.BadZipFile, yaml.YAMLError) as exc:
                errors.append({"repo": repo, "error": str(exc)[:300]})
    return {"schema_version": 1, "generated_at": now(), "skills": records, "complete_repos": successes, "errors": errors}


def sync_catalog(store, sources, scan=False):
    try:
        settings = store.get("settings", "main")
    except KeyError:
        settings = {}
    try:
        if scan or not settings.get("snapshot_repo"):
            payload = scan_sources(sources)
            if not payload["complete_repos"]:
                raise ValueError("；".join(e["error"] for e in payload["errors"]) or "未配置技能来源")
        else:
            repo = settings["snapshot_repo"]
            with httpx.Client(timeout=60, follow_redirects=False) as client:
                page = client.get("https://github.com/" + repo)
                page.raise_for_status()
                match = re.search(r'"currentOid":"([0-9a-f]{40})"', page.text)
                if not match:
                    raise ValueError("快照仓库提交无法核验")
                base = f"https://raw.githubusercontent.com/{repo}/{match[1]}/catalog/"
                raw = client.get(base + "snapshot.json")
                raw.raise_for_status()
                checksum = client.get(base + "snapshot.sha256")
                checksum.raise_for_status()
                import hashlib
                if hashlib.sha256(raw.content).hexdigest() != checksum.text.strip().split()[0]:
                    raise ValueError("目录快照校验失败，保留旧数据")
                payload = raw.json()
        report = store.import_catalog(payload["skills"], payload.get("complete_repos", []))
        report["errors"] = payload.get("errors", [])
        report["status"] = "partial" if report["errors"] else "completed"
        store.save("updates", report)
        stamp = {"id": "sync", "checked_at": now(), "last_success": now(), "status": report["status"]}
        store.save("system", stamp)
        return report
    except Exception as exc:
        report = {"id": uid(), "created_at": now(), "status": "failed", "errors": [{"error": str(exc)[:400]}], "added": [], "changed": [], "removed": []}
        store.save("updates", report)
        try:
            stamp = store.get('system', 'sync')
        except KeyError:
            stamp = {'id':'sync'}
        stamp.update(checked_at=now(), status='failed')
        store.save('system', stamp)
        return report


async def startup_sync(store):
    # At most one attempt per day; startup does not contact paid model providers.
    try:
        config = store.get("settings", "main")
    except KeyError:
        return
    if not config.get("snapshot_repo"):
        return
    try:
        last = store.get("system", "sync")
        if last.get("checked_at", "")[:10] == now()[:10]:
            return
    except KeyError:
        pass
    await asyncio.to_thread(sync_catalog, store, [], False)


def import_local_bundle(store, raw):
    if len(raw) > 20_000_000:
        raise ValueError("本地技能包超过 20MB")
    # A local copy is an independent namespace; upstream updates cannot overwrite it.
    import hashlib
    sha = hashlib.sha1(raw).hexdigest()
    repo = "local/" + sha[:12]
    rows = parse_archive(raw, repo, sha, "UNKNOWN", 0)
    if not rows:
        raise ValueError("ZIP 应包含顶层目录及有效 SKILL.md 和许可证")
    return store.import_catalog(rows)
