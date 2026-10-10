import { useEffect, useState } from 'react';
import HelpPage from './HelpPage';
import { ArrowDownToLine, ArrowRight, BookOpen, Check, ChevronRight, CircleHelp, FlaskConical, FolderOpen, GitCompareArrows, Github, Layers3, LayoutDashboard, Play, Plus, RefreshCw, Search, Settings2, ShieldCheck, Sparkles, X } from 'lucide-react';

type Row = Record<string, any>;
const disciplines = ['通用科研','经济金融','管理与社会科学','计算机与 AI','数学统计','生物医学','化学材料','物理天文','地球环境','工程技术'];
const stages = ['检索','阅读综述','研究设计','数据分析','绘图','写作','引用核验','投稿准备'];
const nav = [{name:'总览',icon:LayoutDashboard},{name:'技能库',icon:BookOpen},{name:'科研项目',icon:FolderOpen},{name:'比较中心',icon:GitCompareArrows},{name:'更新中心',icon:RefreshCw},{name:'设置',icon:Settings2},{name:'使用说明',icon:CircleHelp}];
const date = (v: string) => v ? new Date(v).toLocaleString('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '—';
const statusName: Row = {queued:'等待运行',running:'运行中',completed:'已完成',failed:'失败',partial:'部分完成',cancelled:'已取消',interrupted:'已中断',not_run:'未运行',budget_exhausted:'预算已用尽'};
const money = (v: number) => '¥' + Number(v || 0).toFixed(4);

async function api(path: string, method = 'GET', body?: any): Promise<any> {
  const options: RequestInit = {method};
  if (body instanceof FormData) options.body = body;
  else if (body !== undefined) { options.body = JSON.stringify(body); options.headers = {'Content-Type':'application/json'}; }
  const response = await fetch('/api/v1' + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data;
}

export default function App() {
  const [page, setPage] = useState('总览');
  const [stats, setStats] = useState<Row>({});
  const [config, setConfig] = useState<Row>({});
  const [providers, setProviders] = useState<Row[]>([]);
  const [installed, setInstalled] = useState<Row[]>([]);
  const [projects, setProjects] = useState<Row[]>([]);
  const [runs, setRuns] = useState<Row[]>([]);
  const [updates, setUpdates] = useState<Row[]>([]);
  const [benchmarks, setBenchmarks] = useState<Row[]>([]);
  const [templates, setTemplates] = useState<Row[]>([]);
  const [skills, setSkills] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [sources, setSources] = useState<Row[]>([]);
  const [query, setQuery] = useState('');
  const [discipline, setDiscipline] = useState('');
  const [stage, setStage] = useState('');
  const [sort, setSort] = useState('stars');
  const [offset, setOffset] = useState(0);
  const [onlyInstalled, setOnlyInstalled] = useState(false);
  const [onlyMeasured, setOnlyMeasured] = useState(false);
  const [detail, setDetail] = useState<Row | null>(null);
  const [activeRun, setActiveRun] = useState<Row | null>(null);
  const [activeBenchmark, setActiveBenchmark] = useState<Row | null>(null);
  const [candidateIds, setCandidateIds] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [projectId, setProjectId] = useState('');
  const [files, setFiles] = useState<Row[]>([]);
  const [providerId, setProviderId] = useState('');
  const [selectedSkill, setSelectedSkill] = useState('');
  const [prompt, setPrompt] = useState('');
  const [budget, setBudget] = useState('10');
  const [template, setTemplate] = useState('writing');
  const [mode, setMode] = useState('skills');
  const [modelIds, setModelIds] = useState<string[]>([]);
  const [blind, setBlind] = useState<Row[]>([]);
  const [replacementSlot, setReplacementSlot] = useState('');

  const refresh = async () => {
    const paths = ['/stats','/settings','/providers','/installations','/projects','/runs','/updates','/benchmarks','/benchmarks/templates','/sources'];
    const result = await Promise.all(paths.map(p => api(p)));
    setStats(result[0]); setConfig(result[1]); setProviders(result[2]); setInstalled(result[3]); setProjects(result[4]);
    setRuns(result[5]); setUpdates(result[6]); setBenchmarks(result[7]); setTemplates(result[8]); setSources(result[9]);
  };
  const act = async (task: () => Promise<any>, success = '已保存') => {
    setBusy(true);
    try { const result = await task(); await refresh(); setMessage(success); return result; }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };
  useEffect(() => { refresh().catch(e => setMessage('连接失败：' + e.message)); }, []);
  useEffect(() => {
    let valid = true;
    const params = new URLSearchParams({q:query, discipline, stage, sort, offset:String(offset), limit:'30', installed:String(onlyInstalled), measured:String(onlyMeasured)});
    api('/skills?' + params).then(d => { if(valid) {setSkills(d.items);setTotal(d.total);} }).catch(e => setMessage(e.message));
    return () => {valid = false;};
  }, [query,discipline,stage,sort,offset,onlyInstalled,onlyMeasured,stats.skills]);
  useEffect(() => {
    if (!projectId) return;
    api(`/projects/${projectId}/files`).then(setFiles).catch(e => setMessage(e.message));
  }, [projectId,runs]);
  useEffect(() => {
    if (!activeRun || !['queued','running'].includes(activeRun.status)) return;
    const event = new EventSource(`/api/v1/runs/${activeRun.id}/events`);
    event.onmessage = m => { const r = JSON.parse(m.data);setActiveRun(r); if(!['queued','running'].includes(r.status)) {event.close();refresh().catch(()=>{});} };
    event.onerror = () => event.close();
    return () => event.close();
  }, [activeRun?.id]);
  useEffect(() => {
    if (!benchmarks.some(b => ['queued','running'].includes(b.status)) && !runs.some(r => ['queued','running'].includes(r.status))) return;
    const timer = setInterval(() => {refresh().catch(()=>{}); if(activeBenchmark) api('/benchmarks/' + activeBenchmark.id).then(setActiveBenchmark);}, 2000);
    return () => clearInterval(timer);
  }, [benchmarks,runs,activeBenchmark?.id]);

  const openSkill = async (id: string) => { try {setDetail(await api('/skill?id=' + encodeURIComponent(id)));} catch(e) {setMessage(String(e));} };
  const toggleCandidate = (id: string) => setCandidateIds(ids => ids.includes(id) ? ids.filter(v => v !== id) : [...ids,id]);
  const launch = async () => {
    const r = await act(() => api('/runs','POST',{project_id:projectId,provider_id:providerId,prompt,budget:Number(budget),version_id:selectedSkill || null}), '运行已创建');
    if(r) setActiveRun(r);
  };
  const compare = async () => {
    const r = await act(() => api('/benchmarks','POST',{template,mode,provider_id:providerId,provider_ids:mode === 'models' ? modelIds : [providerId],version_ids:candidateIds,budget:Number(budget),repetitions:3}), '比较已开始');
    if(r) setActiveBenchmark(r);
  };

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><FlaskConical size={23}/></span><div>科研技能工作台<small>RESEARCH WORKBENCH</small></div></div>
      <div className="workspace-label">个人研究空间 <span>LOCAL</span></div>
      <nav aria-label="主导航">{nav.map(n => <button key={n.name} title={n.name} aria-current={page === n.name ? 'page' : undefined} className={page === n.name ? 'nav active' : 'nav'} onClick={() => setPage(n.name)}><n.icon size={18}/>{n.name}{n.name==='更新中心' && updates.length>0 && <span className="nav-count">{updates.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-note"><ShieldCheck size={18}/><div>你的研究，保存在本地<small>资料与执行记录由你掌握</small></div></div><a href="https://github.com/milestonedad-lang/research-skills-workbench" target="_blank" rel="noreferrer"><Github size={16}/> 开源与社区 <ArrowRight size={14}/></a><small className="version">v0.1.0 · 通用科研</small></div>
    </aside>
    <main>
      <header><div className="breadcrumb">研究空间 <ChevronRight size={13}/> <span>{page}</span></div><div className="header-right"><span className="connection"><i/> 本地工作台</span><button className="icon-button" aria-label="刷新数据" onClick={() => act(refresh,'数据已刷新')}><RefreshCw size={16}/></button><span className="avatar">研</span></div></header>
      <div className="content">
        {page === '总览' && <>
          <div className="page-heading"><div><div className="eyebrow">YOUR RESEARCH, IN ONE PLACE</div><h1>让科研工具，成为你的工作流。</h1><p>发现合适的技能，记录真实的效果，让每次选择都有据可查。</p></div><button className="primary" onClick={()=>setPage('科研项目')}><Plus size={17}/> 开始科研任务</button></div>
          <div className="hero"><div><span className="hero-kicker"><Sparkles size={15}/> 为研究而组织</span><h2>从寻找技能<br/>到可复现的研究结果</h2><p>一处检索、执行与比较。固定版本，保留过程，<br/>按你的研究需求选择下一步。</p><button onClick={()=>setPage('技能库')}>探索技能库 <ArrowRight size={17}/></button></div><div className="hero-graphic"><div className="orb orb-one"/><div className="orb orb-two"/><div className="graphic-card card-one"><BookOpen size={20}/><span>发现技能<small>来源与用途可追溯</small></span><Check size={15}/></div><div className="graphic-card card-two"><FlaskConical size={20}/><span>实测比较<small>质量 · 耗时 · 费用</small></span><Layers3 size={17}/></div><div className="graphic-card card-three"><RefreshCw size={20}/><span>持续更新<small>版本固定，随时回退</small></span><Check size={15}/></div><span className="graphic-caption">DISCOVER → RUN → COMPARE → EVOLVE</span></div></div>
          <div className="quickstart-banner"><div><strong>第一次使用？从这里开始</strong><p>浏览技能 → 配置模型 → 创建项目 → 小样例验证 → 下载与复核</p></div><button className="secondary" onClick={()=>setPage('使用说明')}><CircleHelp size={16}/> 阅读首次使用指南</button></div>
          <div className="metrics">{[['收录技能',stats.skills,'条真实来源记录'],['公开仓库',stats.repositories,'保留提交与许可证'],['已安装版本',stats.installed,'按固定版本执行'],['实测技能',stats.measured,'来自已完成的基准运行']].map(([title,value,note])=><div className="metric" key={title}><span>{title}</span><strong>{Number(value || 0).toLocaleString()}</strong><small>{note}</small></div>)}</div>
          <div className="section-heading"><h2>按研究环节开始</h2><button className="text-button" onClick={()=>setPage('技能库')}>查看全部技能 <ArrowRight size={14}/></button></div>
          <div className="stage-grid">{stages.map((s,i)=><button key={s} onClick={()=>{setStage(s);setPage('技能库');setOffset(0);}}><span className="stage-number">0{i+1}</span><h3>{s}</h3><p>{['发现文献与真实来源','梳理研究与证据','构建可验证的方法','从数据得到结果','用图表呈现发现','组织论文与报告','核对引文与元数据','审阅与材料准备'][i]}</p><ArrowRight size={15}/></button>)}</div>
          <div className="overview-bottom"><div className="panel"><div className="section-heading"><h2>最近的科研任务</h2><button className="text-button" onClick={()=>setPage('科研项目')}>查看记录</button></div>{runs.length ? runs.slice(0,3).map(r=><button className="record-line" key={r.id} onClick={()=>{setActiveRun(r);setPage('科研项目');}}><span>{r.prompt.slice(0,42)}</span><Status value={r.status}/></button>) : <Empty title="还没有科研任务" note="创建项目、配置模型后，开始第一次有记录的运行。"/>}</div><div className="panel update-preview"><span className="tag">每月月末 · 21:17</span><h3>目录常新，研究版本由你决定。</h3><p>自动同步公开技能信息。正在使用的版本保持固定，实测后再选择替换。</p><button className="text-button" onClick={()=>setPage('更新中心')}>查看更新设置 <ArrowRight size={14}/></button></div></div>
        </>}
        {page === '技能库' && <>
          <PageTitle eyebrow="SKILL LIBRARY" title="找到适合当前研究的技能" note={`真实收录 ${Number(stats.skills || 0).toLocaleString()} 条 · 去重 ${Number(stats.unique_skills || 0).toLocaleString()} 条。热度只表示关注度。`}/>
          <div className="catalog-layout"><div className="category-panel"><h3>学科门类</h3>{['',...disciplines].map(d=><button className={discipline === d ? 'selected' : ''} key={d} onClick={()=>{setDiscipline(d);setOffset(0);}}>{d || '全部学科'}<ChevronRight size={14}/></button>)}<div className="filter-separator"/><label><input type="checkbox" checked={onlyInstalled} onChange={e=>{setOnlyInstalled(e.target.checked);setOffset(0);}}/> 已安装</label><label><input type="checkbox" checked={onlyMeasured} onChange={e=>{setOnlyMeasured(e.target.checked);setOffset(0);}}/> 已完成实测</label><small>科研用途和适用边界请以详情为准。</small></div><div className="catalog-main"><div className="search-bar"><Search size={18}/><input placeholder="搜索技能、科研用途或仓库…" value={query} onChange={e=>{setQuery(e.target.value);setOffset(0);}}/><select aria-label="排序" value={sort} onChange={e=>setSort(e.target.value)}><option value="stars">关注热度</option><option value="name">名称</option><option value="updated">最近更新</option></select></div><div className="stage-filters">{['',...stages].map(s=><button className={stage===s?'selected':''} key={s} onClick={()=>{setStage(s);setOffset(0);}}>{s || '全部环节'}</button>)}</div><div className="result-heading"><span>找到 <b>{total}</b> 条技能</span>{candidateIds.length>0 && <button className="text-button" onClick={()=>setPage('比较中心')}>比较已选 {candidateIds.length} 个版本 <ArrowRight size={14}/></button>}</div><div className="skill-grid">{skills.map(s=><article className="skill-card" key={s.id}><div className="skill-card-top"><span className="skill-icon"><BookOpen size={18}/></span><span className="tag muted">{s.stage}</span></div><button className="skill-title" onClick={()=>openSkill(s.id)}>{s.name}</button><p className="skill-description">{s.description_zh || s.description}</p>{!s.description_zh && <small className="pending">待中文整理 · 原始说明</small>}<div className="skill-meta"><span>{s.discipline}</span><span>{s.license}</span></div><div className="skill-footer"><span title={s.repo}>{s.repo}</span><button className={candidateIds.includes(s.version_id)?'compare-small picked':'compare-small'} onClick={()=>toggleCandidate(s.version_id)}>{candidateIds.includes(s.version_id)?<Check size={13}/>:<Plus size={13}/>} 比较</button></div></article>)}</div>{!skills.length && <Empty title="没有匹配的技能" note="尝试其他关键词、学科或科研环节。"/>}<div className="pagination"><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-30))}>上一页</button><span>{Math.floor(offset/30)+1} / {Math.max(1,Math.ceil(total/30))}</span><button disabled={offset+30>=total} onClick={()=>setOffset(offset+30)}>下一页</button></div></div></div>
        </>}
        {page === '科研项目' && <>
          <PageTitle eyebrow="RESEARCH PROJECTS" title="把一次研究，变成可检查的过程" note="选择模型和固定技能版本，原始输入会保存快照。"/>
          <div className="two-column"><div className="panel"><h3>任务配置</h3><label>科研项目<select value={projectId} onChange={e=>setProjectId(e.target.value)}><option value="">选择项目</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label><button className="secondary" onClick={()=>{const name=window.prompt('新项目名称');if(name)act(()=>api('/projects','POST',{name}),'项目已创建').then(p=>p&&setProjectId(p.id));}}><Plus size={15}/> 创建项目</button><label>使用模型<select value={providerId} onChange={e=>setProviderId(e.target.value)}><option value="">选择已配置模型</option>{providers.map(p=><option key={p.id} value={p.id}>{p.id} · {p.model}</option>)}</select></label><label>技能版本<select value={selectedSkill} onChange={e=>setSelectedSkill(e.target.value)}><option value="">无技能基线</option>{installed.filter(i=>i.scope==='global'||i.scope===projectId).map(i=><option key={i.slot} value={i.version_id}>{i.name} · {i.commit.slice(0,7)}</option>)}</select></label><label>费用上限（人民币）<input type="number" min="0" step="0.1" value={budget} onChange={e=>setBudget(e.target.value)}/></label><label>科研任务<textarea rows={6} placeholder="描述任务、输入资料、希望获得的结果与验收要求…" value={prompt} onChange={e=>setPrompt(e.target.value)}/></label><button className="primary wide" disabled={busy||!projectId||!providerId||!prompt.trim()} onClick={launch}><Play size={16}/> 开始运行</button>{!providers.length && <p className="hint">先到设置配置模型。离线技能检索不需要密钥。</p>}</div><div className="panel"><h3>项目资料</h3>{projectId ? <><label className="upload"><ArrowDownToLine size={20}/><span>上传 PDF、CSV、Excel 或文档</span><input type="file" onChange={e=>{const f=e.target.files?.[0];if(f){const form=new FormData();form.append('file',f);act(()=>api(`/projects/${projectId}/files`,'POST',form),'原始资料已保存');}e.target.value='';}}/></label>{files.map(f=><a className="file-line" key={f.name} href={`/api/v1/projects/${projectId}/download?path=${encodeURIComponent(f.name)}`}><span>{f.name}</span><small>{Math.ceil(f.size/1024)} KB</small></a>)}</> : <Empty title="先选择科研项目" note="资料和输出按项目保存。原始同名文件不会被覆盖。"/>}</div></div>
          <div className="panel spaced"><h3>运行记录</h3>{runs.length ? <table><thead><tr><th>任务</th><th>模型</th><th>状态</th><th>耗时</th><th>费用估算</th></tr></thead><tbody>{runs.map(r=><tr key={r.id} onClick={()=>setActiveRun(r)} className="clickable"><td>{r.prompt.slice(0,65)}</td><td>{r.actual_model||r.model}</td><td><Status value={r.status}/></td><td>{Number(r.duration||0).toFixed(1)}s</td><td>{money(r.cost)}</td></tr>)}</tbody></table>:<Empty title="还没有运行记录" note="模型响应、工具执行、结果和失败信息将在这里保存。"/>}</div>
          {activeRun && <div className="panel spaced"><div className="section-heading"><h3>运行详情 · {activeRun.id.slice(0,8)}</h3><div><Status value={activeRun.status}/>{['queued','running'].includes(activeRun.status)&&<button className="secondary" onClick={()=>act(()=>api(`/runs/${activeRun.id}/cancel`,'POST',{}),'取消请求已发送').then(r=>r&&setActiveRun(r))}>停止</button>}</div></div>{activeRun.error && <div className="notice">{activeRun.error}</div>}<pre className="output">{activeRun.output || '等待模型或工具返回…'}</pre><div className="artifact-list">{activeRun.artifacts?.map((f:Row)=><a key={f.name} href={`/api/v1/projects/${activeRun.project_id}/download?path=${encodeURIComponent(f.name)}`}><ArrowDownToLine size={14}/>{f.name.split('/').pop()}</a>)}</div><details><summary>执行记录与版本信息</summary><pre>{JSON.stringify(activeRun,null,2)}</pre></details></div>}
        </>}
        {page === '比较中心' && <>
          <PageTitle eyebrow="BENCHMARK & COMPARE" title="先验证质量，再比较效率" note="固定输入、模型参数与运行环境。每个候选默认重复 3 次，并加入无技能基线。"/>
          <div className="two-column"><div className="panel"><h3>创建实测比较</h3><label>比较对象<select value={mode} onChange={e=>setMode(e.target.value)}><option value="skills">同一模型，比较技能或技能版本</option><option value="models">同一技能版本，比较模型</option></select></label><label>公开基准<select value={template} onChange={e=>setTemplate(e.target.value)}>{(templates.length?templates:[{id:'writing',name:'科研写作'}]).map(t=><option value={t.id} key={t.id}>{t.name}{t.requires_docker?' · 需要 Docker':''}</option>)}</select></label>{mode==='skills'?<label>固定模型<select value={providerId} onChange={e=>setProviderId(e.target.value)}><option value="">请选择</option>{providers.map(p=><option key={p.id} value={p.id}>{p.id} · {p.model}</option>)}</select></label>:<div className="checkboxes">{providers.map(p=><label key={p.id}><input type="checkbox" checked={modelIds.includes(p.id)} onChange={()=>setModelIds(ids=>ids.includes(p.id)?ids.filter(x=>x!==p.id):[...ids,p.id])}/>{p.id} · {p.model}</label>)}</div>}<label>此次比较预算上限（人民币）<input type="number" min="0" value={budget} onChange={e=>setBudget(e.target.value)}/></label><p className="hint">免费本地模型可设为 0。付费模型须先配置单价；网络异常可能仍产生服务商费用。</p><button className="primary wide" disabled={busy || (mode==='skills'?!providerId:!modelIds.length)} onClick={compare}><Play size={16}/> 开始实测</button></div><div className="panel"><h3>候选技能版本 <span className="tag">{candidateIds.length}</span></h3><p className="hint">在技能库或技能详情选择候选。同一技能的新旧版本可同时加入。</p>{candidateIds.map(id=><div className="candidate-line" key={id}><span>{installed.find(i=>i.version_id===id)?.name||id.slice(0,16)}</span><button className="icon-button" aria-label="移除候选" onClick={()=>toggleCandidate(id)}><X size={14}/></button></div>)}<button className="text-button" onClick={()=>setPage('技能库')}>去选择技能 <ArrowRight size={14}/></button><div className="notice soft"><ShieldCheck size={18}/><span>科研写作需匿名人工评分；数值、引用和图表保留自动核验说明。未完成实测的技能不参与效果推荐。</span></div></div></div>
          <div className="panel spaced"><h3>实测记录</h3>{!benchmarks.length ? <Empty title="尚无实测结果" note="热度不代表效果。运行同一任务后，才会显示可比较的证据。"/> : benchmarks.map(b=><button className="record-line" key={b.id} onClick={()=>{setActiveBenchmark(b);setBlind([]);}}><span>{templates.find(t=>t.id===b.template)?.name||b.template} · {date(b.created_at)}</span><Status value={b.status}/></button>)}</div>
          {activeBenchmark && <div className="panel spaced"><div className="section-heading"><h3>比较结果</h3>{['queued','running'].includes(activeBenchmark.status)&&<button className="secondary" onClick={()=>act(()=>api(`/benchmarks/${activeBenchmark.id}/cancel`,'POST',{}),'比较已停止').then(b=>b&&setActiveBenchmark(b))}>停止比较</button>}</div>{activeBenchmark.error&&<div className="notice">{activeBenchmark.error}</div>}<table><thead><tr><th>候选</th><th>成功率</th><th>中位耗时</th><th>总费用</th><th>质量状态</th></tr></thead><tbody>{activeBenchmark.ranking?.map((r:Row)=><tr key={r.candidate}><td>{r.candidate==='baseline'?'无技能基线':r.candidate.slice(0,18)}</td><td>{Math.round(r.success_rate*100)}%</td><td>{r.duration.toFixed(2)}s</td><td>{money(r.cost)}</td><td>{r.eligible?'通过此基准检查':'未通过 / 待人工评分'}</td></tr>)}</tbody></table><p className="hint">比较结果仅适用于此次任务及配置。结果不足 3 次、运行失败或质量未达标时不推荐替换。</p><button className="secondary" onClick={()=>api(`/benchmarks/${activeBenchmark.id}/blind`).then(setBlind).catch(e=>setMessage(e.message))}>打开匿名评分</button>{blind.map(b=><div className="blind-output" key={b.label}><h4>{b.label}</h4>{b.images?.map((url:string)=><img key={url} src={url} alt={b.label+" 图表预览"} style={{maxWidth:"100%",maxHeight:500,objectFit:"contain"}}/>)}<pre>{b.output}</pre><label>人工质量评分<select defaultValue={b.score??''} onChange={e=>act(()=>api(`/benchmarks/${activeBenchmark.id}/score`,'POST',{label:b.label,score:Number(e.target.value)}),'评分已记录').then(r=>r&&setActiveBenchmark(r))}><option value="">选择 0—5 分</option>{[0,1,2,3,4,5].map(n=><option key={n} value={n}>{n} 分</option>)}</select></label></div>)}<details><summary>逐次记录与固定配置</summary><pre>{JSON.stringify(activeBenchmark,null,2)}</pre></details></div>}
        </>}
        {page === '更新中心' && <>
          <PageTitle eyebrow="UPDATES & VERSIONS" title="跟进更新，保留你的研究版本" note="月末同步公开目录；已安装版本不会被自动替换。"/>
          <div className="update-banner"><RefreshCw size={26}/><div><h3>每月最后一天 · 北京时间 21:17</h3><p>{config.snapshot_repo?`GitHub ${config.snapshot_repo} 扫描公开来源，本地启动同步快照。`:'发布 GitHub 仓库后，在设置中填写快照仓库即可开启启动同步。'}</p></div><button className="primary" disabled={busy} onClick={()=>act(()=>api('/sync','POST',{scan:false}),'同步检查已结束，请查看报告')}>{busy?<RefreshCw className="spin" size={16}/>:<RefreshCw size={16}/>} 同步目录</button></div>
          <div className="panel spaced"><div className="section-heading"><h3>公开来源</h3><button className="secondary" disabled={busy} onClick={()=>act(()=>api('/sync','POST',{scan:true}),'来源扫描已结束，请查看报告')}>立即扫描来源</button></div>{sources.map(s=><a className="file-line" key={s.repo} href={'https://github.com/'+s.repo} target="_blank" rel="noreferrer"><span><Github size={15}/> {s.repo}</span><small>{s.license}</small></a>)}<button className="text-button" onClick={()=>{const repo=window.prompt('输入 owner/repo 或 GitHub 仓库地址');if(repo)act(()=>api('/sources','POST',{repo}),'来源已添加；点击扫描后导入');}}><Plus size={15}/> 添加 GitHub 仓库</button><label className="inline-upload">导入目录 JSON<input type="file" accept=".json" onChange={e=>{const f=e.target.files?.[0];if(f){const form=new FormData();form.append('file',f);act(()=>api('/catalog/import-file','POST',form),'目录已导入');}e.target.value='';}}/></label><label className="inline-upload">导入个人技能 ZIP<input type="file" accept=".zip" onChange={e=>{const f=e.target.files?.[0];if(f){const form=new FormData();form.append('file',f);act(()=>api('/catalog/local','POST',form),'个人技能已独立收录');}e.target.value='';}}/></label></div>
          <div className="panel spaced"><h3>更新报告</h3>{updates.length ? updates.map(u=><details className="update-row" key={u.id}><summary><span>{date(u.created_at)}</span><span>新增 {u.added?.length||0} · 变更 {u.changed?.length||0} · 失效 {u.removed?.length||0}</span><Status value={u.status||'completed'}/></summary><pre>{JSON.stringify(u,null,2)}</pre></details>):<Empty title="暂无更新记录" note="首次导入和后续同步的差异会保存在这里。同步失败时保留旧目录。"/>}</div>
          <div className="panel spaced"><h3>已安装版本</h3>{installed.filter(i=>i.scope!=='cache').map(i=><div className="installation-line" key={i.slot}><button className="skill-title" onClick={()=>openSkill(i.skill_id)}>{i.name}</button><span className="tag">{i.commit.slice(0,7)} · {i.scope==='global'?'全局':projects.find(p=>p.id===i.scope)?.name||i.scope}</span><a className="text-button" href={`/api/v1/installations/export/${i.version_id}`}>导出</a><button className="secondary" disabled={!i.history.length} onClick={()=>{if(window.confirm('回退此技能？后续任务使用旧版本，当前运行不受影响。'))act(()=>api('/installations/rollback','POST',i),'版本已回退');}}>回退</button></div>)}{!installed.length&&<Empty title="还没有安装技能" note="在详情中核查许可证与依赖后安装。"/>}</div>
        </>}
        {page === '使用说明' && <HelpPage modelCount={providers.length} installedCount={installed.filter(i=>i.scope!=='cache').length} dockerAvailable={config.docker_available} onNavigate={destination=>{setPage(destination);document.querySelector('main')?.scrollIntoView?.({block:'start'});}} onExample={example=>{
          if(prompt.trim() && prompt!==example && !window.confirm('当前有未完成的任务文字。是否用示例替换？项目、模型和预算保持当前选择。')) return;
          setPrompt(example);setPage('科研项目');document.querySelector('main')?.scrollIntoView?.({block:'start'});setMessage('示例已填入草稿；请检查输入、模型和预算，再开始运行。');
        }}/>}
        {page === '设置' && <>
          <PageTitle eyebrow="SETTINGS & SETUP" title="配置你的科研环境" note="模型密钥仅保存在本地后端，不写入公开仓库，也不返回到浏览器。"/>
          <div className="two-column"><div className="panel"><h3>添加或更新模型</h3><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const value=Object.fromEntries(f);act(()=>api('/providers','POST',{...value,input_price:value.input_price===''?null:Number(value.input_price),output_price:value.output_price===''?null:Number(value.output_price)}),'模型配置已保存').then(()=>{(e.target as HTMLFormElement).querySelector<HTMLInputElement>('[name="api_key"]')!.value='';});}}><label>配置名称<input name="id" required placeholder="例如 local 或 deepseek" pattern="[A-Za-z0-9_-]+"/></label><label>接口类型<select name="kind"><option value="openai">OpenAI 兼容接口</option><option value="anthropic">Anthropic</option><option value="ollama">Ollama 本地模型</option></select></label><label>接口地址<input name="base_url" required placeholder="https://服务商地址/v1 或 http://127.0.0.1:11434"/></label><label>模型标识<input name="model" required placeholder="填写服务商提供的模型 ID"/></label><label>API 密钥<input name="api_key" type="password" autoComplete="new-password" placeholder="本地 Ollama 不需要；更新时留空保留旧密钥"/></label><div className="form-row"><label>输入单价<input name="input_price" type="number" min="0" step="any" placeholder="元 / 百万 token"/></label><label>输出单价<input name="output_price" type="number" min="0" step="any" placeholder="元 / 百万 token"/></label></div><label>价格来源<input name="price_source" placeholder="官方价格网址或记录日期"/></label><button className="primary" disabled={busy}>保存模型配置</button></form></div><div><div className="panel"><h3>已配置模型</h3>{providers.map(p=><div className="provider-card" key={p.id}><strong>{p.id}</strong><span className="tag">{p.kind}</span><p>{p.model}</p><small>{p.base_url}</small><button className="text-button" onClick={()=>act(()=>api(`/providers/${p.id}/test`,'POST',{}),'连接已检查').then(r=>r&&setMessage('可用模型：'+r.models.join('、')))}>检查连接与模型列表</button></div>)}{!providers.length&&<Empty title="配置首个模型" note="有 API 密钥即可使用远程模型；有本地模型可选择 Ollama。"/>}</div><div className="panel spaced"><h3>代码执行环境</h3><div className="notice soft"><ShieldCheck size={20}/>{config.docker_available?'检测到 Docker 命令；运行时会检查服务和镜像。':'尚未检测到 Docker。文本类任务可以使用；代码任务需要完成下列安装。'}</div><p className="hint">安装并启动 Docker Desktop，然后在项目根目录运行：</p><pre className="command">docker build -t research-workbench-runner:0.1.0 -f docker/runner.Dockerfile .</pre><a className="text-button" href="https://docs.docker.com/desktop/setup/install/windows-install/" target="_blank" rel="noreferrer">Docker Windows 安装说明 <ArrowRight size={14}/></a></div><div className="panel spaced"><h3>GitHub 快照同步</h3><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);act(()=>api('/settings','POST',{...config,snapshot_repo:f.get('snapshot_repo')}),'快照设置已保存');}}><label>公共仓库<input key={config.snapshot_repo} name="snapshot_repo" defaultValue={config.snapshot_repo} placeholder="milestonedad-lang/research-skills-workbench"/></label><p className="hint">配置后启动自动检查公共目录快照；私人资料不会同步到 GitHub。</p><button className="secondary">保存同步设置</button></form></div></div></div>
        </>}
        <footer>科研技能工作台 <span>发现 · 验证 · 复现</span><button className="text-button" onClick={()=>setPage('使用说明')}><CircleHelp size={13}/> 打开使用说明</button></footer>
      </div>
    </main>
    {detail && <div className="modal-backdrop" onClick={()=>setDetail(null)}><div className="detail-modal" role="dialog" aria-label="技能详情" onClick={e=>e.stopPropagation()}><button className="close" aria-label="关闭详情" onClick={()=>setDetail(null)}><X size={20}/></button><span className="eyebrow">SKILL DETAILS</span><h2>{detail.name}</h2><p>{detail.description_zh||detail.description}</p><div className="detail-tags"><span className="tag">{detail.discipline}</span><span className="tag">{detail.stage}</span><span className="tag">{detail.license}</span><span className="tag">{detail.translation_status||'中文用途'}</span></div><a className="source-link" href={detail.source_url||`https://github.com/${detail.repo}/blob/${detail.commit}/${detail.path}`} target="_blank" rel="noreferrer"><Github size={15}/>{detail.repo} · {detail.commit.slice(0,12)}</a><div className="notice soft">{detail.compatibility||'请检查技能正文与脚本依赖。'}</div><p className="hint">{detail.tutorial||'安装固定版本，在科研项目中选择技能，先用公开样例验证输出。'}</p><div className="detail-actions">{detail.installable===false&&<div className="notice">仅索引来源：{detail.missing_resources?.length?`资源超过打包限制：${detail.missing_resources.join("、")}`:"许可证尚未明确允许安装，请核对上游条款。"}</div>}<button className="primary" disabled={busy||detail.installable===false} onClick={()=>act(()=>api('/installations','POST',{skill_id:detail.id}),'固定版本已安装')}>安装当前版本</button><button className="secondary" onClick={()=>toggleCandidate(detail.version_id)}>{candidateIds.includes(detail.version_id)?'移出比较':'加入比较'}</button><label className="inline-select">项目级安装<select defaultValue="" onChange={e=>{if(e.target.value)act(()=>api('/installations','POST',{skill_id:detail.id,scope:e.target.value}),'项目版本已安装');}}><option value="">选择项目</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></label></div><h3>版本与替换</h3><div className="panel spaced"><label>替代已安装技能<select value={replacementSlot} onChange={e=>setReplacementSlot(e.target.value)}><option value="">选择要替代的技能</option>{installed.filter(i=>i.scope!=='cache'&&i.skill_id!==detail.id).map(i=><option value={i.slot} key={i.slot}>{i.name} · {i.scope==='global'?'全局':projects.find(p=>p.id===i.scope)?.name||i.scope}</option>)}</select></label><p className="hint">对照原文、依赖与比较中心的实测证据。替代仅影响后续任务，旧技能可在更新中心回退。</p><button className="secondary" disabled={!replacementSlot||busy} onClick={()=>{const previous=installed.find(i=>i.slot===replacementSlot);if(previous&&window.confirm(`将 ${previous.name} 替代为 ${detail.name}？新包检查成功后生效，保留旧版本。`))act(()=>api('/installations/switch','POST',{skill_id:detail.id,version_id:detail.version_id,slot:previous.slot,scope:previous.scope,expected:previous.version_id}),'技能已替代，可在更新中心回退').then(()=>setReplacementSlot(''));}}>确认替代</button></div>{detail.versions?.map((v:Row)=><div className="installation-line" key={v.version_id}><span>{v.commit.slice(0,12)} · {date(v.fetched_at)}</span><button className="text-button" onClick={()=>toggleCandidate(v.version_id)}>{candidateIds.includes(v.version_id)?'已选比较':'加入比较'}</button><button className="secondary" onClick={()=>{if(window.confirm('切换全局版本？后续任务使用所选版本，旧版本可回退。'))act(()=>api('/installations/switch','POST',{skill_id:detail.id,version_id:v.version_id}),'版本已切换');}}>切换</button></div>)}<details><summary>手动翻译中文用途</summary><label>翻译模型<select value={providerId} onChange={e=>setProviderId(e.target.value)}><option value="">请选择</option>{providers.map(p=><option key={p.id} value={p.id}>{p.id} · {p.model}</option>)}</select></label><label>此次翻译预算（人民币）<input type="number" min="0" value={budget} onChange={e=>setBudget(e.target.value)}/></label><p className="hint">仅翻译公开用途说明；付费模型按配置单价计费，译文标记待复核。</p><button className="secondary" disabled={!providerId||busy} onClick={()=>act(()=>api('/catalog/translate','POST',{provider_id:providerId,skill_ids:[detail.id],budget:Number(budget)}),'翻译已保存，请复核用途边界').then(()=>openSkill(detail.id))}>开始翻译</button></details><details open><summary>技能原文与工作流程</summary><pre className="skill-body">{detail.body || '此内容仅索引来源；许可证尚未明确允许收录全文与安装。'}</pre></details></div></div>}
    {message && <div className="toast" role="status"><span>{message}</span><button aria-label="关闭提示" onClick={()=>setMessage('')}><X size={16}/></button></div>}
  </div>;
}

function PageTitle({eyebrow,title,note}:{eyebrow:string;title:string;note:string}) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{note}</p></div></div>; }
function Empty({title,note}:{title:string;note:string}) {return <div className="empty"><Layers3 size={24}/><strong>{title}</strong><p>{note}</p></div>;}
function Status({value}:{value:string}) {return <span className={'status '+value}>{statusName[value]||value}</span>;}
