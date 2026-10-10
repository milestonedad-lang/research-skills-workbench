import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, expect, test, vi } from 'vitest';
import App from './App';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ ok: true, json: async () => url.includes('stats') ? { skills: 177, repositories: 2, unique_skills: 170, installed: 0, runs: 0, measured: 0 } : url.includes('skills?') ? { items: [{id:'a',name:'literature-review',description_zh:'文献综述与证据核验',discipline:'通用科研',stage:'阅读综述',license:'MIT',stars:10,version_id:'v1',repo:'lab/skills',commit:'a'.repeat(40)}], total:1 } : url.includes('settings') ? {docker_available:false, snapshot_repo:'', display_name:'科研技能工作台'} : url.includes('benchmarks/templates') ? [] : [] })));
});
afterEach(() => vi.unstubAllGlobals());
test('catalog displays real metadata and searchable Chinese purpose', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', {name:'技能库'}));
  expect(await screen.findByText('文献综述与证据核验')).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText('搜索技能、科研用途或仓库…'), {target:{value:'文献'}});
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining('q=%E6%96%87%E7%8C%AE'), expect.anything()));
});
test('comparison starts with an unmeasured state rather than a fabricated leaderboard', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', {name:'比较中心'}));
  expect(await screen.findByText(/尚无实测结果/)).toBeInTheDocument();
});

test('user can replace an installed skill only after reviewing and confirming the target', async () => {
  const originalFetch = globalThis.fetch;
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (url:string, options:any) => {
    if (url === '/api/v1/installations' && options?.method === 'GET') return {ok:true,json:async()=>[{slot:'global:old',skill_id:'old',name:'旧综述工具',version_id:'old-v',scope:'global',commit:'b'.repeat(40),history:[]}]};
    if (url.includes('/skill?id=')) return {ok:true,json:async()=>({id:'a',name:'literature-review',description_zh:'文献综述与证据核验',version_id:'v1',commit:'a'.repeat(40),repo:'lab/skills',versions:[],installable:true})};
    return originalFetch(url, options);
  }));
  render(<App />);
  fireEvent.click(screen.getByRole('button',{name:'技能库'}));
  fireEvent.click(await screen.findByRole('button',{name:'literature-review'}));
  fireEvent.change(await screen.findByLabelText('替代已安装技能'),{target:{value:'global:old'}});
  fireEvent.click(screen.getByRole('button',{name:'确认替代'}));
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('技能已替代'));
});
