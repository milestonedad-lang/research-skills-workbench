# 架构、接口与可追溯记录

React / TypeScript / Vite 前端由 FastAPI 提供静态资源；SQLite WAL 存储技能版本、安装选择与任务记录。首版单用户，仅监听 loopback，检查 Host 与 Origin。

## 数据边界

| 目录 | 内容 | 是否公开 |
|---|---|---|
| `server/`、`web/`、`scripts/` | 原创应用代码 | 是 |
| `catalog/` | 来源注册表、授权内容和固定 SHA 公共快照 | 是，保留各上游许可证 |
| `examples/`、`tests/` | 公开样例与独立测试数据 | 是 |
| `data/` | 个人 SQLite、密钥、资料、安装包、运行记录 | 否 |
| `.local/`、`.venv/`、`web/dist/` | 本地开发验证、依赖、构建物 | 否 |

Skill 来源 ID 由仓库与真实路径组成。SkillVersion 包含提交 SHA、正文 hash、资源 hash 与许可证。Installation 保存 slot、作用域、固定版本和历史。Run 保存输入快照、工具调用、模型配置、实际模型标识、预算、环境与成果哈希。BenchmarkResult 关联固定输入与批次配置。

模型密钥使用 Fernet 加密存储，主密钥和数据库共同位于个人数据目录。运行与比较内部保存加密配置快照，公开接口剔除密钥。加密不替代主机与备份权限控制。

## API

所有接口以 `/api/v1` 开头；启动后 `/docs` 可查看完整 OpenAPI。

| 范围 | 主要接口 |
|---|---|
| 基础 | `GET /health`、`/stats`、`/taxonomy` |
| 目录 | `GET /skills`、`/skill?id=...`、`/version/{id}` |
| 来源和同步 | `GET/POST /sources`、`POST /sync`、`GET /updates` |
| 导入 | `POST /catalog/import`、`/catalog/import-file`、`/catalog/local` |
| 翻译 | `POST /catalog/translate`，显式模型与预算 |
| 安装与回退 | `GET/POST /installations`、`POST /installations/switch`、`/installations/rollback` |
| 导出 | `GET /installations/export/{version_id}` |
| 项目 | `GET/POST /projects`、`GET/POST /projects/{id}/files`、`GET /projects/{id}/download` |
| 模型 | `GET/POST /providers`、`POST /providers/{id}/test` |
| 任务 | `GET/POST /runs`、`GET /runs/{id}`、`/runs/{id}/events`（SSE）、`POST /runs/{id}/cancel` |
| 基准 | `GET /benchmarks/templates`、`GET/POST /benchmarks`、详情、cancel、blind、score |
| 推荐与设置 | `GET /recommendations`、`GET/POST /settings` |

## 执行器

模型使用 JSON 动作协议：读取资料、读取技能资源、Crossref 检索/DOI 核验、Docker Python、保存文本、最终报告。按需读取相对资源；首版每次最多 30 步、输出 token 最多 8192，默认 12 步/2048。读取限制用于控制上下文和开销。

容器固定镜像 ID，禁网、只读系统、输入只读、非 root、2 CPU/2GB/128进程，单次代码超时120秒。输出独立挂载，stdout/stderr 有内存保留上限。技能专用依赖不自动联网安装。runner 镜像构建依赖会随重建变化，实际任务记录镜像摘要用于追溯。

预算在每次模型请求前以输入字节上界及输出上限预留，SQLite 事务避免并发超预留。响应用量已知时按配置单价结算，异常或未知用量按预留保守结算。token 定义、价格更新和服务商额外收费可能使账单与估算不同。

## 同步和比较

扫描固定 GitHub 提交归档，验证路径与大小，保守判断许可证。失败来源沿用旧快照；成功来源可以标记失效条目，安装历史不删除。启动同步每天最多尝试一次，手动入口仍可补检。公共快照通过 SHA-256 文件核验。

比较创建时冻结模型配置与环境，在首个请求前冻结各试验输入。每个批次独立排序，质量检查优先；人工评分对科研写作与绘图生效。推荐只使用完成、至少三次且质量通过的结果，不跨任务推广。
