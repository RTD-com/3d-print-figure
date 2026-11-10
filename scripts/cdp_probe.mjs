#!/usr/bin/env node
/** CDP 探针：启动本机 Edge/Chrome（headless、独立 profile），确认 /json/version 可访问，然后清理。
 *  输出 JSON：{ ok, browser, wsUrl?, error? }。供 preflight.ps1 调用，也用于排查 hunyuan_web.mjs 环境问题。 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';

const edge = ['C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', 'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'].find((p) => fs.existsSync(p));
const chrome = ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'].find((p) => fs.existsSync(p));
const exe = edge || chrome;
const out = { ok: false, browser: exe || null, error: null };

async function alive(port) {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(1500) });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

async function main() {
  if (!exe) throw new Error('未找到 Edge/Chrome');
  let port = 9341;
  for (let i = 0; i < 10; i++, port++) if (!(await alive(port))) break;
  const profile = path.join(os.tmpdir(), 'dsh-cdp-probe-' + Math.random().toString(16).slice(2));
  fs.mkdirSync(profile, { recursive: true });
  const child = spawn(exe, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-address=127.0.0.1', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
  ], { detached: true, stdio: 'ignore' });
  try {
    let info = null;
    for (let i = 0; i < 40 && !info; i++) {
      await new Promise((r) => setTimeout(r, 500));
      info = await alive(port);
    }
    if (!info?.webSocketDebuggerUrl) throw new Error(`CDP 端口 ${port} 在 20s 内未就绪`);
    out.ok = true;
    out.port = port;
    out.wsUrl = info.webSocketDebuggerUrl;
    out.version = info.Browser;
  } finally {
    if (child.pid) spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* ignore */ }
  }
}

main()
  .catch((e) => { out.error = String(e?.message || e); })
  .finally(() => {
    console.log(JSON.stringify(out));
    process.exit(0);
  });
