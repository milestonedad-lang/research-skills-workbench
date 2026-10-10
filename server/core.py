"""Persistence, immutable skill versions and transactional spending limits."""
import calendar
import hashlib
import json
import math
import os
import re
import sqlite3
import statistics
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

DISCIPLINES = ["通用科研", "经济金融", "管理与社会科学", "计算机与 AI", "数学统计", "生物医学", "化学材料", "物理天文", "地球环境", "工程技术"]
STAGES = ["检索", "阅读综述", "研究设计", "数据分析", "绘图", "写作", "引用核验", "投稿准备"]


class BudgetExceeded(ValueError):
    """Reservation rejected before a paid request is sent."""


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return uuid.uuid4().hex


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_month_end(value):
    local = value.astimezone(timezone(timedelta(hours=8)))
    return local.day == calendar.monthrange(local.year, local.month)[1]


def safe_path(root, relative):
    p = PurePosixPath(relative)
    if not relative or "\\" in relative or ":" in relative or p.is_absolute() or any(x in {"..", "."} for x in relative.split("/")):
        raise ValueError("文件路径无效")
    result = (Path(root) / str(p)).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError("文件越界")
    return result


def rank_results(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["candidate"], []).append(row)
    result = []
    for candidate, items in grouped.items():
        passed = [i for i in items if i["status"] == "completed" and i.get("quality", 0) >= 1]
        result.append({"candidate": candidate, "samples": len(items), "success_rate": len(passed) / len(items),
                       "eligible": len(passed) == len(items), "quality": statistics.mean(i.get("quality", 0) for i in items),
                       "duration": statistics.median(i["duration"] for i in items),
                       "duration_range": [min(i["duration"] for i in items), max(i["duration"] for i in items)],
                       "cost": sum(i.get("cost", 0) for i in items), "errors": [i.get("error") for i in items if i.get("error")]})
    return sorted(result, key=lambda x: (not x["eligible"], x["duration"], x["cost"]))


class Store:
    def __init__(self, path):
        self.root = Path(path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "workbench.sqlite3"
        with self.connect() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY, version_id TEXT, name TEXT, description TEXT,
              description_zh TEXT, discipline TEXT, stage TEXT, repo TEXT, stars INTEGER, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY, skill_id TEXT, body TEXT, record TEXT);
            CREATE INDEX IF NOT EXISTS versions_skill ON versions(skill_id);
            CREATE TABLE IF NOT EXISTS installations(slot TEXT PRIMARY KEY, skill_id TEXT, version_id TEXT, scope TEXT, history TEXT);
            CREATE TABLE IF NOT EXISTS entities(kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS budgets(id TEXT PRIMARY KEY, cap REAL, spent REAL DEFAULT 0, reserved REAL DEFAULT 0);
            """)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def save(self, kind, item):
        with self.connect() as c:
            c.execute("INSERT OR REPLACE INTO entities VALUES(?,?,?)", (kind, item["id"], json.dumps(item, ensure_ascii=False)))
        return item

    def get(self, kind, identity):
        with self.connect() as c:
            r = c.execute("SELECT value FROM entities WHERE kind=? AND id=?", (kind, identity)).fetchone()
        if not r:
            raise KeyError(identity)
        return json.loads(r[0])

    def list(self, kind):
        with self.connect() as c:
            return [json.loads(r[0]) for r in c.execute("SELECT value FROM entities WHERE kind=? ORDER BY rowid DESC", (kind,))]

    def import_catalog(self, records, complete_repos=()):
        prepared = []
        for raw in records:
            r = dict(raw)
            for field in ("id", "name", "repo", "path", "commit", "content_hash", "body"):
                if not isinstance(r.get(field), str):
                    raise ValueError(f"缺少字段 {field}")
            if not re.fullmatch(r"[0-9a-f]{40}", r["commit"]) or digest(r["body"]) != r["content_hash"]:
                raise ValueError("提交 SHA 或内容校验失败")
            if not re.fullmatch(r"[\w.-]+/[\w.-]+", r["repo"]):
                raise ValueError("仓库标识无效")
            safe_path(self.root, r["path"])
            if r["id"] != r["repo"] + "/" + r["path"].removesuffix("/SKILL.md"):
                raise ValueError("技能标识与来源不一致")
            bundle = r.get("bundle", {})
            if not isinstance(bundle, dict) or len(bundle) > 2000:
                raise ValueError("技能包格式无效")
            for path, content in bundle.items():
                safe_path(self.root, path)
                if not isinstance(content, str) or len(content.encode()) > 2_000_000:
                    raise ValueError("技能包文件超出限制")
            r.setdefault("description", "")
            r.setdefault("description_zh", "")
            r.setdefault("discipline", "通用科研")
            r.setdefault("stage", "研究设计")
            r.setdefault("stars", 0)
            r.setdefault("license", "UNKNOWN")
            r.setdefault("fetched_at", now())
            r["bundle_hash"] = digest(json.dumps(bundle, sort_keys=True, ensure_ascii=False))
            r["version_id"] = digest(r["id"] + r["commit"] + r["content_hash"] + r["bundle_hash"])[:32]
            prepared.append(r)
        report = {"id": uid(), "created_at": now(), "added": [], "changed": [], "version_changes": [], "dependency_changes": [], "license_changes": [], "removed": [], "errors": []}
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            for r in prepared:
                prior = c.execute("SELECT version_id FROM skills WHERE id=?", (r["id"],)).fetchone()
                if not prior:
                    report["added"].append(r["id"])
                elif prior[0] != r["version_id"]:
                    report['version_changes'].append(r['id'])
                    previous = json.loads(c.execute("SELECT record FROM versions WHERE id=?", (prior[0],)).fetchone()[0])
                    if any(previous.get(k) != r.get(k) for k in ('body', 'bundle', 'bundle_encodings')):
                        report['changed'].append(r['id'])
                    if previous.get("license") != r["license"]:
                        report["license_changes"].append(r["id"])
                    if previous.get("compatibility") != r.get("compatibility") or previous.get("dependencies") != r.get("dependencies"):
                        report["dependency_changes"].append(r["id"])
                c.execute("INSERT OR IGNORE INTO versions VALUES(?,?,?,?)", (r["version_id"], r["id"], r["body"], json.dumps(r, ensure_ascii=False)))
                c.execute("INSERT OR REPLACE INTO skills VALUES(?,?,?,?,?,?,?,?,?,1)", tuple(r[k] for k in ("id", "version_id", "name", "description", "description_zh", "discipline", "stage", "repo", "stars")))
            incoming = {r["id"] for r in prepared}
            for repo in complete_repos:
                for row in c.execute("SELECT id FROM skills WHERE repo=? AND active=1", (repo,)).fetchall():
                    if row[0] not in incoming:
                        report["removed"].append(row[0])
                        c.execute("UPDATE skills SET active=0 WHERE id=?", (row[0],))
            c.execute("INSERT INTO entities VALUES('updates',?,?)", (report["id"], json.dumps(report, ensure_ascii=False)))
        return report

    def search(self, q="", discipline="", stage="", installed=False, limit=30, offset=0, sort="stars", measured=False):
        clauses, args = ["s.active=1"], []
        if q:
            clauses.append("(s.name LIKE ? OR s.description LIKE ? OR s.description_zh LIKE ? OR s.repo LIKE ?)")
            args.extend(["%" + q + "%"] * 4)
        for field, value in (("discipline", discipline), ("stage", stage)):
            if value:
                clauses.append(f"s.{field}=?")
                args.append(value)
        if installed:
            clauses.append("EXISTS(SELECT 1 FROM installations i WHERE i.skill_id=s.id AND i.scope!='cache')")
        if measured:
            ids = {r.get("skill_id") for r in self.list("runs") if r.get("benchmark_id") and r.get("status") == "completed"}
            clauses.append("s.id IN (" + ",".join("?" for _ in ids) + ")" if ids else "0")
            args.extend(ids)
        where = " AND ".join(clauses)
        order = {"stars": "s.stars DESC,s.name", "name": "s.name", "updated": "json_extract(v.record,'$.fetched_at') DESC,s.name"}.get(sort, "s.stars DESC,s.name")
        with self.connect() as c:
            total = c.execute(f"SELECT COUNT(*) FROM skills s WHERE {where}", args).fetchone()[0]
            rows = c.execute(f"SELECT v.record FROM skills s JOIN versions v ON v.id=s.version_id WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            items = []
            for row in rows:
                r = json.loads(row[0])
                items.append({k: v for k, v in r.items() if k not in {"body", "bundle"}})
        return {"total": total, "items": items}

    def version(self, identity):
        with self.connect() as c:
            r = c.execute("SELECT record FROM versions WHERE id=?", (identity,)).fetchone()
        if not r:
            raise KeyError(identity)
        return json.loads(r[0])

    def skill(self, identity):
        with self.connect() as c:
            r = c.execute("SELECT version_id FROM skills WHERE id=?", (identity,)).fetchone()
            if not r:
                raise KeyError(identity)
            versions = [json.loads(x[0]) for x in c.execute("SELECT record FROM versions WHERE skill_id=? ORDER BY rowid DESC", (identity,))]
        return {**self.version(r[0]), "versions": [{k: v for k, v in x.items() if k not in {"body", "bundle"}} for x in versions]}

    def install(self, identity, version_id=None, scope="global", slot=None, expected=None):
        r = self.version(version_id) if version_id else self.skill(identity)
        if r["id"] != identity:
            raise ValueError("版本与技能不一致")
        if r.get('installable') is False or r.get('missing_resources'):
            raise ValueError('此技能仅索引来源或资源包不完整，不能安装')
        if r.get("license", "UNKNOWN") not in {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "CC0-1.0"}:
            raise ValueError("许可证未明确允许安装，请核对上游条款")
        if not r.get("bundle") or "SKILL.md" not in r["bundle"]:
            raise ValueError("技能仅收录目录，尚无可安装完整包")
        import yaml
        skill_text = r["bundle"]["SKILL.md"]
        if not skill_text.startswith("---"):
            raise ValueError("缺少技能元数据")
        metadata = yaml.safe_load(skill_text.split("---", 2)[1])
        if not isinstance(metadata, dict) or not metadata.get("name") or not metadata.get("description"):
            raise ValueError("技能元数据校验失败")
        directory = self.root / "installed" / r["version_id"]
        if not directory.exists():
            staging = self.root / "installed" / ("staging-" + uid())
            staging.mkdir(parents=True)
            try:
                for name, body in r["bundle"].items():
                    dest = safe_path(staging, name)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if r.get("bundle_encodings", {}).get(name) == "base64":
                        import base64
                        dest.write_bytes(base64.b64decode(body, validate=True))
                    else:
                        dest.write_bytes(body.encode("utf-8"))
                # Immutable destination; concurrent successful installation is reusable.
                try:
                    os.rename(staging, directory)
                except FileExistsError:
                    import shutil
                    shutil.rmtree(staging)
            except BaseException:
                import shutil
                if staging.exists():
                    shutil.rmtree(staging)
                raise
        # A cached directory is trusted only while every pinned byte is intact.
        import base64
        expected_files = set(r["bundle"])
        actual_files = {str(p.relative_to(directory)).replace("\\", "/") for p in directory.rglob("*") if p.is_file()}
        if actual_files != expected_files:
            raise ValueError("安装包文件已变化，请导入为个人技能或恢复固定版本")
        for name, content in r["bundle"].items():
            expected_bytes = base64.b64decode(content, validate=True) if r.get("bundle_encodings", {}).get(name) == "base64" else content.encode("utf-8")
            path = safe_path(directory, name)
            if path.is_symlink() or path.read_bytes() != expected_bytes:
                raise ValueError("安装包校验失败，不能按原版本执行")
        slot = slot or scope + ":" + identity
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            prior = c.execute("SELECT version_id,history FROM installations WHERE slot=?", (slot,)).fetchone()
            if expected is not None and (not prior or prior[0] != expected):
                raise ValueError("安装状态已变化，请刷新后重试")
            history = json.loads(prior[1]) if prior else []
            if prior and prior[0] != r["version_id"]:
                history.append(prior[0])
            c.execute("INSERT OR REPLACE INTO installations VALUES(?,?,?,?,?)", (slot, identity, r["version_id"], scope, json.dumps(history)))
        return {"slot": slot, "skill_id": identity, "version_id": r["version_id"], "scope": scope, "history": history, "commit": r["commit"]}

    def installations(self):
        with self.connect() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM installations")]
        for r in rows:
            r["history"] = json.loads(r["history"])
            r["commit"] = self.version(r["version_id"])["commit"]
            r["name"] = self.version(r["version_id"])["name"]
        return rows

    def rollback(self, identity, scope="global", slot=None):
        slot = slot or scope + ":" + identity
        prior = next((r for r in self.installations() if r["slot"] == slot), None)
        if not prior or not prior["history"]:
            raise ValueError("没有可回退版本")
        r = self.version(prior["history"][-1])
        return self.install(r["id"], r["version_id"], scope, slot, expected=prior["version_id"])

    def create_budget(self, identity, limit):
        if not math.isfinite(limit) or limit < 0:
            raise ValueError("预算必须是非负有限数值")
        with self.connect() as c:
            c.execute("INSERT INTO budgets(id,cap) VALUES(?,?)", (identity, limit))

    def budget(self, identity):
        with self.connect() as c:
            row = c.execute("SELECT * FROM budgets WHERE id=?", (identity,)).fetchone()
        if not row:
            raise KeyError(identity)
        return dict(row)

    def reserve(self, identity, amount):
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("费用无效")
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM budgets WHERE id=?", (identity,)).fetchone()
            if not r or r["spent"] + r["reserved"] + amount > r["cap"] + 1e-9:
                raise BudgetExceeded("预算上限已达到，无法预留下一次请求费用")
            c.execute("UPDATE budgets SET reserved=reserved+? WHERE id=?", (amount, identity))

    def settle(self, identity, reserved, actual):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE budgets SET reserved=MAX(0,reserved-?),spent=spent+? WHERE id=?", (reserved, actual, identity))
