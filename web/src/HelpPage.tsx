import { ArrowRight, BookOpen, Check, CircleHelp, ShieldCheck } from 'lucide-react';

type HelpProps = {
  modelCount: number;
  installedCount: number;
  dockerAvailable?: boolean;
  onNavigate: (page: string) => void;
  onExample: (prompt: string) => void;
};

const repository = 'https://github.com/milestonedad-lang/research-skills-workbench';
const sections = [
  ['prepare', '首次使用'], ['models', '模型与代码环境'], ['run', '执行与下载'],
  ['examples', '科研任务示例'], ['compare', '比较与替换'], ['sync', '月末更新'], ['faq', '常见问题与备份'],
];
const examples = [
  {
    title: '研究设计与写作审阅', action: '填入写作任务', requirement: '需要模型 · 无需 Docker',
    note: '先填写你的研究问题，或上传研究设计草稿。适合检验模型是否遵守事实边界。',
    prompt: '请审阅我的研究设计草稿。先列出资料中明确给出的研究问题、样本与方法，再检查研究问题与方法是否匹配、变量定义是否清晰、有哪些混杂因素及伦理事项。用“原文依据—问题—修改建议”组织 Markdown 报告；没有提供的信息标为“待补充”，不要编造样本量、结果、显著性或参考文献。若尚未上传草稿，请先列出我需要补充的信息。',
  },
  {
    title: '文献检索与 DOI 核验', action: '填入文献任务', requirement: '需要模型 · 需要联网',
    note: '将示例主题换成你的研究主题。工具使用 Crossref，覆盖范围不等同于所有学术数据库。',
    prompt: '围绕“highway infrastructure inspection”检索相关学术文献，使用文献检索和 DOI 核验工具，选取最多 5 条能核实的记录。逐条列出标题、作者、年份、DOI、来源链接和核验状态，说明筛选依据及数据库覆盖限制。没有摘要或全文时不要推断研究结论；没有可核验来源时明确写出，不要编造引用。输出 Markdown 文献清单。',
  },
  {
    title: '数据分析与统计绘图', action: '填入数据分析任务', requirement: '需要模型 · 需要 Docker',
    note: '先上传源码 examples/analysis/sample.csv，或将任务中的文件名、变量名改为实际资料。',
    prompt: '读取项目资料 sample.csv，检查 value 列的数据类型与缺失值，计算有效样本数、均值和样本标准差（ddof=1），说明缺失值处理。使用 Python 实际执行计算，保存 summary.csv、包含轴标签与单位说明的 distribution.png、可复运行的 analysis.py 到 /outputs，并生成 Markdown 分析报告。保留原始数据，不要虚构执行结果；若代码环境或输入缺失，明确报告原因。',
  },
];

export default function HelpPage({ modelCount, installedCount, dockerAvailable, onNavigate, onExample }: HelpProps) {
  return <div className="help-page">
    <div className="page-heading"><div><div className="eyebrow">RESEARCH WORKBENCH GUIDE</div><h1>从第一次使用，到可复现的研究</h1><p>按步骤配置、执行和核验。此说明随应用保存在本地，可离线阅读。</p></div></div>
    <nav className="help-toc" aria-label="使用说明目录">{sections.map(([id, label]) => <a href={'#help-' + id} key={id}>{label}</a>)}</nav>

    <section id="help-prepare" className="panel help-section" aria-labelledby="prepare-title">
      <h2 id="prepare-title"><BookOpen size={20}/> 01 · 首次使用</h2>
      <p>首次启动双击项目根目录的 <code>start.cmd</code>，等待依赖安装和界面构建，再打开 <code>http://127.0.0.1:8765</code>。首次准备需要联网；启动完成后，已收录目录的检索和本页说明可离线使用。</p>
      <div className="help-readiness">
        <div><Check size={17}/><strong>目录与版本管理</strong><span>无需模型密钥；下载和同步需要联网</span></div>
        <div><CircleHelp size={17}/><strong>{modelCount ? `已保存 ${modelCount} 个模型配置` : '尚未配置模型'}</strong><span>保存后到设置检查连接；任务执行需要可用模型</span></div>
        <div><ShieldCheck size={17}/><strong>{dockerAvailable === undefined ? '正在检查代码环境' : dockerAvailable ? '检测到 Docker 命令' : '尚未检测到 Docker'}</strong><span>代码任务还需 Docker 服务与运行镜像</span></div>
      </div>
      <p>推荐先用公开样例完成一次运行，再放入正式研究资料。当前已安装 {installedCount} 个使用槽位；也可以选择“无技能基线”试运行，建立比较参照。</p>
      <div className="help-actions"><button className="primary" onClick={() => onNavigate('设置')}>去配置模型 <ArrowRight size={15}/></button><button className="secondary" onClick={() => onNavigate('技能库')}>浏览技能库</button></div>
    </section>

    <section id="help-models" className="panel help-section" aria-labelledby="models-title">
      <h2 id="models-title">02 · 配置模型与代码环境</h2>
      <p>在“设置 → 添加或更新模型”填写配置名称、接口类型、接口地址、实际模型 ID 与密钥。配置名称只用英文、数字、下划线或短横线；用同一名称保存可更新该配置，更新时密钥留空保留原密钥。</p>
      <div className="help-table"><table><thead><tr><th>接口类型</th><th>地址与准备</th></tr></thead><tbody>
        <tr><td>OpenAI 兼容</td><td>使用服务商公布的基础地址，通常以 <code>/v1</code> 结尾；填写该服务商的模型 ID 与 API 密钥。</td></tr>
        <tr><td>Anthropic</td><td>官方基础地址为 <code>https://api.anthropic.com/v1</code>；填写实际可用的模型 ID 与密钥。</td></tr>
        <tr><td>Ollama</td><td>本机通常为 <code>http://127.0.0.1:11434</code>；先启动 Ollama 并下载所选模型，填写与本机一致的模型名，不需密钥。</td></tr>
      </tbody></table></div>
      <p>保存后点击“检查连接与模型列表”。该检查不能保证每个模型都能完成任务，应继续用简单文本任务验证。ChatGPT 订阅与服务商 API 额度分别管理。</p>
      <div className="notice soft">付费模型必须配置人民币／百万 token 的输入、输出单价及价格来源；服务商按美元报价时先换算。不要把付费模型设成 0 元。免费本地模型可设单价及预算为 0。运行费用是本地估算，需与服务商账单核对。</div>
      <h3>需要计算或生成图表时</h3>
      <p>安装并启动 Docker Desktop，在项目根目录终端执行以下命令。第一条构建运行镜像，第二条检查实际计算、绘图和输入只读条件。</p>
      <pre className="command">{'docker build -t research-workbench-runner:0.1.0 -f docker/runner.Dockerfile .\n.venv\\Scripts\\python.exe scripts\\runner_smoke.py'}</pre>
      <p>基础镜像包含常用科研依赖。特殊技能的依赖需要另行检查。默认 Docker Compose 部署没有连接主机 Docker，代码任务请按部署指南使用主机后端与独立运行容器。</p>
      <a className="text-button" href="https://docs.docker.com/desktop/setup/install/windows-install/" target="_blank" rel="noreferrer">Docker Windows 安装说明 <ArrowRight size={14}/></a>
    </section>

    <section id="help-run" className="panel help-section" aria-labelledby="run-title">
      <h2 id="run-title">03 · 从选择技能到下载成果</h2>
      <ol className="help-steps">
        <li><strong>发现并核对。</strong>在技能库组合中文或英文关键词、学科、科研环节与安装状态筛选。查看原文、来源提交、许可证和依赖；热度与收录数量不代表效果。“仅索引来源”的条目不能直接安装。</li>
        <li><strong>安装固定版本。</strong>详情中点击“安装当前版本”，或先创建项目再选择“项目级安装”。安装需要获取技能包；安装完毕后不会自动跟随上游更新。</li>
        <li><strong>创建项目并上传。</strong>到科研项目创建项目，选择后上传 PDF、CSV、Excel、DOCX 或文本。记录实际文件名；同名资料不会覆盖，更新资料请改名。</li>
        <li><strong>定义任务与验收。</strong>选择模型、技能版本或无技能基线，填写任务、输入文件、变量定义、方法、输出格式与核验要求，再设置此次预算。确认资料可以发送给所选模型服务商。</li>
        <li><strong>执行并查看过程。</strong>点击“开始运行”。运行记录保存固定版本、模型、输入与工具调用；点击记录查看详情。任务需要计算时必须具备代码环境。失败时先阅读错误，避免重复付费尝试。</li>
        <li><strong>下载并核验。</strong>运行详情中的文件链接用于下载。默认报告为 Markdown 和 DOCX；CSV、PNG、PDF 与脚本需要任务实际生成。结合数据、方法、引用和代码复核结果后再用于研究。</li>
      </ol>
      <p>首版 PDF 读取最多前 50 页、最多 4 万字符，不含 OCR。扫描型 PDF 请先识别文字；长文档应拆分并说明范围，避免把局部阅读当成全文结论。</p>
      <div className="help-actions"><button className="secondary" onClick={() => onNavigate('科研项目')}>打开科研项目 <ArrowRight size={15}/></button></div>
    </section>

    <section id="help-examples" className="panel help-section" aria-labelledby="examples-title">
      <h2 id="examples-title">04 · 可修改的科研任务示例</h2>
      <p>点击按钮只会把文字填入任务草稿。请调整主题、资料和验收要求，选择项目、模型与预算后自行开始运行。</p>
      <div className="help-examples">{examples.map(example => <article key={example.action} className="help-example">
        <h3>{example.title}</h3><span className="tag">{example.requirement}</span><p>{example.note}</p><pre>{example.prompt}</pre>
        <button className="secondary" onClick={() => onExample(example.prompt)}>{example.action} <ArrowRight size={14}/></button>
      </article>)}</div>
    </section>

    <section id="help-compare" className="panel help-section" aria-labelledby="compare-title">
      <h2 id="compare-title">05 · 实测比较、替换与回退</h2>
      <ol className="help-steps">
        <li>在技能库点击“比较”，或详情中“加入比较”；同一技能的不同版本可从版本记录加入。</li>
        <li>到比较中心选择文献与引用、数据分析、统计绘图或科研写作基准。比较技能固定模型；比较模型需固定一个技能版本。每个候选默认运行三次，技能比较还包含无技能基线。</li>
        <li>填写整个批次的预算。数据分析与绘图需 Docker，引用核验需联网。失败计入成功率，预算不足会停止后续运行。</li>
        <li>先看质量和成功率，再比较中位耗时、波动与费用。科研写作和图表语义需打开匿名评分，按基准要求打分；少于三次或未通过质量检查的结果不作为替换推荐。</li>
      </ol>
      <h3>选择生效范围，再确认切换</h3>
      <p>同一技能升级：在详情“版本与替换”核对版本后点击“切换”（此按钮切换全局版本）；项目专用版本通过“项目级安装”指定项目。不同技能替代：打开新技能详情，选择要替代的已安装槽位，核对依赖与实测证据，再“确认替代”。项目槽位影响该项目，全局槽位影响使用全局选择的后续任务。</p>
      <p>新包基本检查成功后生效，运行中的任务继续使用原版本。需要恢复时，到“更新中心 → 已安装版本”找到对应槽位，点击“回退”。旧版本仍保留；没有历史时回退按钮不可用。自行改动的技能先导出、编辑并重新导入个人 ZIP，避免被上游更新覆盖。</p>
      <div className="help-actions"><button className="secondary" onClick={() => onNavigate('比较中心')}>打开比较中心</button><button className="secondary" onClick={() => onNavigate('更新中心')}>查看版本与回退</button></div>
    </section>

    <section id="help-sync" className="panel help-section" aria-labelledby="sync-title">
      <h2 id="sync-title">06 · 启用月末更新</h2>
      <ol className="help-steps">
        <li>在自己的 GitHub 仓库将应用开发分支合并到默认分支 <code>main</code>，启用 Actions，并按部署指南配置工作流写入权限。定时工作流必须位于默认分支才会触发。</li>
        <li>在工作台“设置 → GitHub 快照同步”填写 <code>milestonedad-lang/research-skills-workbench</code>；使用 fork 时改为自己的 <code>owner/repo</code>。</li>
        <li>GitHub 每月最后一天北京时间 21:17 扫描公开来源。本地启动时检查新快照，每天最多自动检查一次；电脑关机期间由 GitHub 执行扫描，下次启动再同步。</li>
        <li>需要补检时，到更新中心点击“同步目录”获取快照；“立即扫描来源”直接扫描公开来源。查看更新报告中的新增、内容／依赖／许可证变化和来源失效。</li>
      </ol>
      <p>扫描不调用付费模型，不上传私人资料，也不会自动替换已安装技能。网络错误、限流或部分来源失败时查看报告，保留旧目录；GitHub 定时任务可能延迟或因长期无活动停用，可在仓库 Actions 手动恢复或运行。</p>
    </section>

    <section id="help-faq" className="panel help-section help-faq" aria-labelledby="faq-title">
      <h2 id="faq-title">07 · 常见问题、隐私与备份</h2>
      <details><summary>开始运行按钮不可用，或模型请求失败</summary><p>确认已选择项目和模型，并填写非空任务。到设置核对接口类型、地址、实际模型 ID 与密钥，检查连接；认证失败查密钥，限流查服务商配额。付费模型还需要价格来源与足够预算。保存配置或查看模型列表不能替代真实任务验证。</p></details>
      <details><summary>有 Docker 命令，但计算或绘图仍失败</summary><p>启动 Docker Desktop，确认运行镜像已经构建，执行本页的 smoke 命令。查看运行详情中的工具错误；缺少专用依赖需另行构建镜像。容器代码默认不能联网，外部数据应先通过允许的工具获取或上传，输入目录只读，结果保存到 /outputs。</p></details>
      <details><summary>任务没有读到 PDF，或缺少期望的成果文件</summary><p>核对文件是否上传到当前项目、任务中的文件名是否匹配，以及 PDF 是否包含可抽取文字。长文档受读取范围限制。报告默认提供 Markdown 与 DOCX；图表、CSV、PDF 和脚本只有实际执行生成后才有下载链接，可在任务里指定文件名及输出要求。</p></details>
      <details><summary>取消或失败后是否还会收费</summary><p>停止按钮终止后续工作，但已发送给服务商的请求可能仍计费。平台保留失败与取消记录；用量缺失时按预留金额保守记账，估算可能高于实际费用。结合服务商账单与额度上限管理费用。</p></details>
      <details><summary>为什么更新后技能仍是旧版本，比较没有优胜推荐</summary><p>目录更新与安装版本分离。需要在详情核对新旧版本、完成可比实测后主动切换。热度不参与效果判断；失败、质量未达标、未完成人工评分或运行不足三次时不会给出替换推荐，不同配置的批次也不合并排名。</p></details>
      <details><summary>资料发到哪里，如何备份和换电脑</summary><p>资料与运行记录保存在本机 data/。远程模型会收到任务及按工具读取的资料；本地 Ollama 在本机处理。密钥加密保存在后端，其主密钥也在 data/，请保护整个目录。备份前停止任务和服务，再复制整个 data/ 到私人备份位置；换电脑时安装相同版本应用，停止服务后恢复整个目录。不要将 data/、密钥或私人备份上传 GitHub。</p></details>
      <div className="help-actions"><a className="text-button" href={repository + '/blob/feature/workbench-v0.1/docs/USER_GUIDE.md'} target="_blank" rel="noreferrer">完整使用手册 <ArrowRight size={14}/></a><a className="text-button" href={repository + '/blob/feature/workbench-v0.1/docs/DEPLOYMENT.md'} target="_blank" rel="noreferrer">部署与 GitHub 指南 <ArrowRight size={14}/></a><a className="text-button" href={repository + '/issues'} target="_blank" rel="noreferrer">反馈问题 <ArrowRight size={14}/></a></div>
    </section>
  </div>;
}
