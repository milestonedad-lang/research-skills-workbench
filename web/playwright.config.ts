import { defineConfig } from '@playwright/test';
import path from 'node:path';
export default defineConfig({
  testDir:'./e2e',
  use:{baseURL:'http://127.0.0.1:8766',viewport:{width:1440,height:1100},channel:process.env.WORKBENCH_BROWSER || undefined},
  webServer:{command:(process.platform==='win32'?`"${path.resolve('../.venv/Scripts/python.exe')}"`:'python')+' -m uvicorn server.main:app --app-dir .. --host 127.0.0.1 --port 8766',url:'http://127.0.0.1:8766/api/v1/health',reuseExistingServer:false,env:{WORKBENCH_DATA:'../.local/e2e-data'}},
  workers:1,reporter:'list'
});
