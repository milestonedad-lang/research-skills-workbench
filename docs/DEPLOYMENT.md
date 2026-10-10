# 部署与 GitHub 分支指南

首次使用建议选择 Windows 本机部署。GitHub 保存源码与公共技能目录；完整平台需要 Python 后端，GitHub Pages 无法执行科研任务。

## 1. 本机启动

安装 [Python 3.12+](https://www.python.org/downloads/)、[Node.js 24](https://nodejs.org/) 和 [Git](https://git-scm.com/downloads)。首次安装 Python 时选中 Add Python to PATH。代码分析和绘图另外安装 [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)，启用 WSL 2 并启动 Docker。

已有本地源码时，进入 `D:\科研研究平台`，双击 `start.cmd`。首次启动需要联网安装依赖与构建界面，窗口出现地址后打开：

**http://127.0.0.1:8765**

终端窗口保持打开，按 Ctrl+C 停止服务。无需模型密钥即可浏览和检索已收录技能。

从 GitHub 下载时，在仓库左上角分支选择器选择 `feature/workbench-v0.1`，点击 Code → Download ZIP，解压后双击 `start.cmd`。或使用下面的命令，把 `你的账号/你的仓库` 换成真实仓库名称：

```powershell
git clone --branch feature/workbench-v0.1 https://github.com/你的账号/你的仓库.git
cd 你的仓库
powershell -ExecutionPolicy Bypass -File start.ps1
```

## 2. 接入模型

打开“设置”，添加模型配置。名称用字母、数字或下划线。

| 接口类型 | 地址示例 | 需要准备 |
|---|---|---|
| OpenAI 兼容 | 服务商提供的完整接口基础地址，通常以 `/v1` 结束 | 模型 ID、API 密钥、输入/输出单价 |
| Anthropic | `https://api.anthropic.com/v1` | 模型 ID、API 密钥、输入/输出单价 |
| Ollama | `http://127.0.0.1:11434` | 已安装 Ollama 并下载的模型名称 |

本地 Ollama 不需要密钥，运行预算可以设为 0。付费接口价格单位为人民币/百万 token；服务商若用美元计价，需要先换算并记录日期与价格来源。保存后点击“检查连接与模型列表”。模型必须能遵循 JSON 工具协议；仅能聊天的模型未必能完成科研流程。

## 3. 启用 CSV/Excel 分析和绘图

在项目根目录打开 PowerShell：

```powershell
docker build -t research-workbench-runner:0.1.0 -f docker/runner.Dockerfile .
.venv\Scripts\python.exe scripts\runner_smoke.py
```

第二条命令会实际读取样例 CSV、计算均值、生成 PNG，并检查输入只读。输出 `status: passed` 后再运行代码任务。构建镜像不会调用模型。科研任务仍需所选模型生成代码。

## 4. 上传开发分支

开发分支用于试用和审查，默认分支用于公开稳定版本。仓库空白时应先有一个初始化提交，再创建开发分支。若已有工作分支与本地提交，只需关联你的仓库并推送：

当前专属仓库是 `milestonedad-lang/research-skills-workbench`。本地已准备好分支后，在 PowerShell 执行：

```powershell
Set-Location -LiteralPath 'D:\科研研究平台'
git push -u origin main
git push -u origin feature/workbench-v0.1
```

GitHub登录时使用有写入权限的 `milestonedad-lang` 账号。main 初始提交仅提供项目入口，完整平台位于开发分支；核对检查结果后再合并。若使用Codex连接器上传，也必须授权拥有仓库写入权限的账号。

其他使用者可按下列通用方式关联自己的仓库：

```powershell
git remote add origin https://github.com/你的账号/你的仓库.git
git push -u origin feature/workbench-v0.1
```

如果 origin 已存在，先 `git remote -v` 核对地址，不要重复添加。推送时按 Git 的登录提示完成 GitHub 认证，密钥不应填写到源码文件中。

在 GitHub 点击 Compare & pull request，检查 Platform checks 的测试结果。通过后将开发分支合并到默认分支。月末定时 Actions 只有默认分支中的工作流会自动执行，因此仅推送开发分支不会启用自动月末扫描。

## 5. 开启月末更新

1. 默认分支包含 `.github/workflows/catalog-update.yml`。
2. GitHub → Actions，允许工作流运行；Settings → Actions → General → Workflow permissions 允许该工作流写入目录快照。如果默认分支受保护，需调整规则允许快照提交，或改成更新 PR 流程。
3. 在 Actions 中打开 Monthly public skills catalog → Run workflow，先手动扫描一次。
4. 本地平台“设置 → GitHub 快照同步”填入公共仓库的 `owner/repo`。
5. “更新中心 → 同步目录”，核对新增、变更和失败信息。

计划时间为每月最后一天北京时间 21:17。28—31 日触发后程序判断月末；GitHub 可能延迟执行，长期无活动的公共仓库可能停用定时工作流。恢复 Actions 后可以手动补扫。同步失败保留旧目录；安装版本不自动替换。

## 6. Linux / macOS

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock.txt
cd web
npm ci
npm run build
cd ..
python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

代码任务仍需构建 runner。Linux 会使用后端当前用户 UID/GID 启动非 root 运行容器；以 root 启动后端时使用 nobody 并仅调整独立输出目录所有者。

## 7. Docker Compose

```sh
docker compose up --build -d
docker compose logs -f
```

打开 http://127.0.0.1:8765。此部署支持技能目录与远程模型文本流程，默认没有 Docker daemon socket，不能启动代码任务 runner。Ollama 使用宿主 loopback 的配置也无法直接从容器访问；本地 Ollama 与代码任务优先使用主机部署。平台首版仅供单用户本机使用。

## 8. 数据备份与版本更新

关闭服务后备份整个 `data/`：数据库、加密密钥、资料、成果与运行记录共同保留。Compose 数据保存在 `workbench-data` volume。不要把数据目录上传 GitHub。

更新源码后，在项目目录重新安装锁定依赖并构建前端：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
cd web
npm.cmd ci
npm.cmd run build
cd ..
```

随后启动服务。技能目录更新、技能版本切换和应用源码更新是三种不同操作。

## 常见问题

| 现象 | 检查与处理 |
|---|---|
| 找不到 Python 或 npm | 重新打开终端，运行 `python --version`、`node --version`；按上文安装依赖 |
| 端口 8765 被占用 | 关闭旧服务；也可手动启动 uvicorn 时改 `--port 8767` |
| Docker 命令存在但任务失败 | 确认 Desktop 已启动，运行 `docker info`，构建镜像并运行 smoke 检查 |
| 技能只能看来源，不能安装 | 许可证不明确或资源包不完整；核对上游授权，不能用平台许可证代替 |
| 预算不足 | 查看已花费和保守预留值，缩小任务/输出或重新设定预算；不得自动绕过预算 |
| 月末没有更新 | 查看 Actions 是否启用、默认分支是否含工作流、网络错误或限流；手动 Run workflow |
| 模型返回不适合工具调用 | 更换支持结构化响应的模型；运行详情保留原始返回与错误 |

