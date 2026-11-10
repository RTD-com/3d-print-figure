#!/usr/bin/env node
/**
 * hunyuan_web.mjs — 混元 3D 网页自动化（自研 CDP 脚本，零依赖）
 *
 * 设计（Q5b）：Node 24 内置 WebSocket 直连本机 Edge/Chrome 的 CDP；可见窗口 + 专用 profile；
 * 不装浏览器扩展、不装 DSH 插件、不下载 Playwright 内核。
 *
 * 模式：
 *   --mode probe     打开页面，抓 DOM/截图/file input/按钮/额度文本，用于校准选择器（首次必跑）
 *   --mode upload    检查登录 → 读额度 → 逐槽上传8图 → 配置回读 → 证据（绝不提交）
 *   --mode submit    固定路径确认文件/图像哈希 → 逐槽检查 → 额度/配置复验 → 提交/任务绑定/下载
 *   --mode status    读当前页面状态/额度/任务进度
 *   --mode download  只下载已有结果
 *
 * 退出码：0成功；2参数；10确认；11任务上下文；12额度；13配置/生成/GLB；14浏览器；15登录；16上传；17已存在；20其它。
 *
 * 注意：混元页面结构可能变化。首次运行先 probe，按 2.DSH/04-浏览器记录/probe/ 结果更新
 * assets/templates/hunyuan-selectors.json；不要把本文件当“永不失效”的爬虫。
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

export const EXIT = { OK: 0, USAGE: 2, CONFIRM: 10, CONTEXT: 11, QUOTA: 12, GEN_FAIL: 13, NEED_BROWSER: 14, LOGIN: 15, UPLOAD: 16, EXISTS: 17, ERROR: 20 };
export const VIEWS = [
  ['top', '01_top.png', '上传顶图'], ['left45', '02_left45.png', '上传左45°图'],
  ['front', '03_front.png', '上传正图'], ['right45', '04_right45.png', '上传右45°图'],
  ['left', '05_left.png', '上传左图'], ['right', '06_right.png', '上传右图'],
  ['back', '07_back.png', '上传背图'], ['bottom', '08_bottom.png', '上传底图'],
].map(([slot, file, label]) => ({ slot, file, label }));
const MODES = ['probe', 'wait-login', 'upload', 'submit', 'status', 'download'];
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ---------- CLI ----------
const argv = process.argv.slice(2);
function flag(name) { return argv.includes(`--${name}`); }
function opt(name, def = undefined) {
  const i = argv.indexOf(`--${name}`);
  if (i === -1) return def;
  const v = argv[i + 1];
  return v === undefined || v.startsWith('--') ? true : v;
}
const mode = String(opt('mode', 'probe'));
const projectRoot = typeof opt('project') === 'string' ? path.resolve(opt('project')) : null;
const workdir = projectRoot ? path.dirname(path.dirname(projectRoot)) : null;
const recordDir = projectRoot ? path.join(projectRoot, '2.DSH', '04-浏览器记录') : null;
const viewsRoot = projectRoot ? path.join(projectRoot, '3.图片') : null;
const canonicalImages = viewsRoot ? path.join(viewsRoot, 'v1') : null;
const imagesDir = typeof opt('images') === 'string' ? path.resolve(opt('images')) : canonicalImages;
const HUNYUAN_ORIGIN = 'https://3d.hunyuan.tencent.com';
const url = String(opt('url', HUNYUAN_ORIGIN + '/creation'));
const browserKind = String(opt('browser', 'edge'));
const headed = !flag('headless');
const dryRun = flag('dry-run');
const force = flag('force');
const timeoutMin = Number(opt('timeout-min', 30));
const intervalSec = Number(opt('interval-sec', 15));
const profileDir = workdir ? path.resolve(String(opt('profile', path.join(workdir, '.browser-profiles', 'hunyuan')))) : null;
const selectorsPath = path.resolve(String(opt('selectors', path.join(__dirname, '..', 'assets', 'templates', 'hunyuan-selectors.json'))));
const outRoot = projectRoot ? path.resolve(String(opt('out-dir', path.join(projectRoot, '4.模型文件', '4.1初版')))) : null;
const metadataPath = outRoot ? path.join(outRoot, 'metadata.json') : null;

const stamp = () => new Date().toISOString().replace(/[:.]/g, '-');
const log = (...a) => console.error('[hunyuan]', ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const readJson = (p, d) => { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return d; } };
const writeJson = (p, v) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, JSON.stringify(v, null, 2), 'utf8'); };
let selectors = {};
function anyText(list, fallback = []) { return [...(list || []), ...fallback].filter(Boolean); }
function matchAny(text, words) { return words.some((w) => text.includes(w)); }
function stop(code, message) { const e = new Error(message); e.exitCode = code; throw e; }
function hunyuanPage(value) {
  try {
    const parsed = new URL(value);
    return parsed.origin === HUNYUAN_ORIGIN && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}
function cdnResource(value) {
  try {
    const parsed = new URL(value);
    return hunyuanPage(value) || (parsed.protocol === 'https:' && !parsed.port &&
      !parsed.username && !parsed.password && parsed.hostname.endsWith('.myqcloud.com'));
  } catch {
    return false;
  }
}
function localDebugger(value, port) {
  const parsed = new URL(value);
  if (parsed.protocol !== 'ws:' || parsed.hostname !== '127.0.0.1' ||
      Number(parsed.port) !== port || parsed.username || parsed.password) {
    stop(EXIT.NEED_BROWSER, 'CDP 调试连接必须指向指定的本机端口');
  }
  return parsed.href;
}
export function parseQuota(value) {
  const s = String(value ?? '').trim();
  return /^\d+$/.test(s) && Number.isSafeInteger(Number(s)) ? Number(s) : null;
}
export function validateSubmitQuota(value, quotaBefore) {
  if (!Number.isSafeInteger(value) || value < 1) stop(EXIT.QUOTA, '提交前额度未知或不足1，禁止提交');
  if (value !== quotaBefore) stop(EXIT.CONFIRM, '页面额度与用户确认 quotaBefore 不匹配，请重新确认');
  return value;
}
export function validateConfirmation(c, expected) {
  if (!c || typeof c.confirmedAt !== 'string' || !Number.isFinite(Date.parse(c.confirmedAt)) || Date.parse(c.confirmedAt) > Date.now() + 60000) stop(EXIT.CONFIRM, 'confirmedAt 缺失/无效');
  if (typeof c.project !== 'string' || path.resolve(c.project) !== path.resolve(expected.project)) stop(EXIT.CONFIRM, '确认 project 不匹配');
  if (!Array.isArray(c.imageSha256) || c.imageSha256.length !== 8 || c.imageSha256.some((h, i) => !/^[a-f0-9]{64}$/.test(h) || h !== expected.imageSha256[i])) stop(EXIT.CONFIRM, '确认 imageSha256 必须按8槽绑定当前批准版本的图片');
  if (!Number.isSafeInteger(c.quotaBefore) || c.quotaBefore < 1) stop(EXIT.CONFIRM, '确认 quotaBefore 必须为正整数');
  if (!c.modelVersion || c.modelVersion !== expected.modelVersion || !Number.isSafeInteger(c.faces) || c.faces !== expected.faces || c.generateType !== expected.generateType) stop(EXIT.CONFIRM, '确认版本/面数/生成类型不匹配');
  return c;
}
export function confirmationDigest(c) {
  const identity = [
    path.resolve(c.project),
    new Date(c.confirmedAt).toISOString(),
    c.imageSha256,
    c.quotaBefore,
    c.modelVersion,
    c.faces,
    c.generateType,
  ];
  return createHash('sha256').update(JSON.stringify(identity)).digest('hex');
}
function previouslyAttempted(dir, confirmedAt) {
  return fs.readdirSync(dir)
    .filter(name => /^submit-used-[a-f0-9]{64}\.json$/.test(name))
    .some(name => {
      const used = readJson(path.join(dir, name), null);
      const submittedAt = Date.parse(used?.submittedAt);
      return !Number.isFinite(submittedAt) || Date.parse(confirmedAt) <= submittedAt;
    });
}
// 逐槽门禁：顺序/身份/缩略图/完成态必须同时成立；显式给出的“新图证据”字段必须是 true，
// 任何 false 或 'unknown' 都视为未证明（A04：旧缩略图或不可证明的完成态不得放行）。
const SLOT_EVIDENCE_KEYS = ['fileMatchesExpected', 'fileMatchesExpectedHash', 'thumbnailUpdated', 'thumbnailMatchesFile', 'serverComplete'];
export function uploadsComplete(slots) {
  if (!Array.isArray(slots) || slots.length !== 8) return false;
  return VIEWS.every((v, i) => {
    const s = slots[i];
    if (!s || s.slot !== v.slot || s.file !== v.file || s.thumbnail !== true || s.complete !== true || s.uploading !== false) return false;
    return SLOT_EVIDENCE_KEYS.every((k) => !(k in s) || s[k] === true);
  });
}
export function inspectGlb(buf) {
  if (buf.length <= 1048576 || buf.subarray(0, 4).toString('ascii') !== 'glTF' || buf.readUInt32LE(4) !== 2 || buf.readUInt32LE(8) !== buf.length) stop(EXIT.GEN_FAIL, 'GLB magic/version/大小/声明长度校验失败（要求 >1 MiB）');
  return { bytes: buf.length, sha256: createHash('sha256').update(buf).digest('hex') };
}
function guardTarget(target) {
  if (fs.existsSync(target) && !force) stop(EXIT.EXISTS, `目标已存在，请指定新的 --out-dir 版本目录（显式 --force 才可覆盖）：${target}`);
}
function loadConfirmation() {
  const raw = opt('confirm-file');
  if (typeof raw !== 'string') stop(EXIT.CONFIRM, 'submit 必须提供 --confirm-file <项目内2.DSH/03-确认/submit-confirmation.json>');
  const expected = path.join(projectRoot, '2.DSH', '03-确认', 'submit-confirmation.json');
  const candidate = path.resolve(raw);
  if (candidate !== expected || !fs.existsSync(candidate) || fs.realpathSync(candidate) !== candidate) stop(EXIT.CONFIRM, '确认文件必须为项目内固定路径，不能通过符号链接越界');
  const c = readJson(candidate, null);
  if (!c || typeof c.modelVersion !== 'string' || !c.modelVersion.trim() || !Number.isSafeInteger(c.faces) || c.faces < 1 || c.generateType !== 'Normal') stop(EXIT.CONFIRM, '确认配置不完整；网页实际为 Normal，Geometry API 的 Q6b 待定');
  return { c, file: candidate };
}
function inspectImages() {
  const cfg = selectors.upload;
  if (!cfg || cfg.expectedInputs !== 8 || typeof cfg.fileInputSelector !== 'string' || !Number.isFinite(cfg.maxBytes) || !Number.isFinite(cfg.minEdge)) stop(EXIT.UPLOAD, '上传配置缺失或不是8槽');
  const accepted = cfg.accept.split(',').map(s => s.trim().toLowerCase());
  return VIEWS.map(v => {
    const file = path.join(imagesDir, v.file);
    if (!fs.existsSync(file) || (mode === 'submit' && fs.realpathSync(file) !== file)) stop(EXIT.UPLOAD, `图片缺失或为链接：${file}`);
    const buf = fs.readFileSync(file);
    if (!accepted.includes(path.extname(file).toLowerCase()) || buf.length > cfg.maxBytes) stop(EXIT.UPLOAD, `图片类型/大小不符合限制：${v.file}`);
    if (buf.length < 24 || buf.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a' || buf.toString('ascii', 12, 16) !== 'IHDR') stop(EXIT.UPLOAD, `预期有效PNG：${v.file}`);
    const width = buf.readUInt32BE(16), height = buf.readUInt32BE(20);
    if (Math.min(width, height) < cfg.minEdge) stop(EXIT.UPLOAD, `图片小于 ${cfg.minEdge}px：${v.file}`);
    return { ...v, path: file, bytes: buf.length, width, height, sha256: createHash('sha256').update(buf).digest('hex') };
  });
}
export function checkedContext(value) {
  if (!value?.taskId || !value?.resultPageUrl || !Number.isFinite(Date.parse(value.submittedAt))) stop(EXIT.CONTEXT, '缺少 metadata.json 中的 taskId/resultPageUrl/submittedAt；禁止新开任务');
  let u;
  try { u = new URL(value.resultPageUrl); } catch { stop(EXIT.CONTEXT, '结果页URL无效'); }
  const routeId = u.pathname.match(/\/(?:task|result|detail)\/([^/]+)/i)?.[1];
  const ids = [u.searchParams.get('taskId'), u.searchParams.get('task_id'), u.searchParams.get('id'), routeId];
  if (!hunyuanPage(u.href) || !ids.some(id => id && decodeURIComponent(id) === String(value.taskId))) stop(EXIT.CONTEXT, '结果页 URL 无法绑定 taskId');
  return value;
}

// ---------- 浏览器启动 ----------
function browserCandidates() {
  if (browserKind === 'chrome') {
    return ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'];
  }
  return ['C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'];
}
function findBrowser() {
  const explicit = browserKind.includes('\\') ? browserKind : null;
  if (explicit) return explicit;
  for (const p of browserCandidates()) if (fs.existsSync(p)) return p;
  throw new Error('找不到 Edge/Chrome，请用 --browser <路径> 指定');
}
async function portAlive(port) {
  try { const r = await fetch(`http://127.0.0.1:${port}/json/version`, { redirect: 'error', signal: AbortSignal.timeout(1500) }); return r.ok; }
  catch { return false; }
}
async function ensureBrowser(initialUrl = url) {
  const requested = Number(opt('port', 9229));
  if (await portAlive(requested)) return { port: requested, exe: 'existing' };
  let port = requested;
  for (let i = 0; i < 10; i++, port++) if (!(await portAlive(port))) break;
  const exe = findBrowser();
  fs.mkdirSync(profileDir, { recursive: true });
  const args = [
    '--remote-debugging-address=127.0.0.1',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--no-first-run', '--no-default-browser-check', '--disable-features=Translate',
    ...(headed ? ['--start-maximized'] : ['--headless=new']),
    initialUrl,
  ];
  log('launch', exe, `port=${port}`, `profile=${profileDir}`);
  const child = spawn(exe, args, { detached: true, stdio: 'ignore' });
  child.unref();
  for (let i = 0; i < 60; i++) {
    if (await portAlive(port)) return { port, exe };
    await sleep(500);
  }
  const err = new Error(
    `浏览器 CDP 未就绪（port ${port}）。如果当前会话受命令沙箱限制，浏览器可能无法启动：` +
    `请在项目外双击 scripts\\start_browser.bat（或由用户在自己的终端运行 scripts\\start_browser.ps1）启动一次浏览器，` +
    `再用 --port ${port} 重跑本脚本。`);
  err.code = 'NEED_BROWSER';
  throw err;
}

// ---------- CDP ----------
class CDP {
  constructor(wsUrl) { this.wsUrl = wsUrl; this.id = 0; this.pending = new Map(); this.ws = null; this.listeners = new Map(); }
  async open() {
    await new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(new Error(`WebSocket error: ${e?.message || 'unknown'}`));
    });
    this.ws.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.method) for (const fn of this.listeners.get(msg.method) || []) fn(msg.params);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error))); else resolve(msg.result);
      }
    };
  }
  on(method, fn) {
    const list = this.listeners.get(method) || []; list.push(fn); this.listeners.set(method, list);
    return () => this.listeners.set(method, list.filter(x => x !== fn));
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  close() { try { this.ws?.close(); } catch { /* ignore */ } }
}
async function connectBrowser(port) {
  const info = await (await fetch(`http://127.0.0.1:${port}/json/version`, { redirect: 'error', signal: AbortSignal.timeout(5000) })).json();
  const browser = new CDP(localDebugger(info.webSocketDebuggerUrl, port)); await browser.open();
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`, { redirect: 'error', signal: AbortSignal.timeout(5000) })).json();
  const pageInfo = list.find((t) => t.type === 'page' && hunyuanPage(t.url)) || list.find((t) => t.type === 'page');
  if (!pageInfo?.webSocketDebuggerUrl) throw new Error('没有可用的 page target');
  const page = new CDP(localDebugger(pageInfo.webSocketDebuggerUrl, port)); await page.open();
  return { browser, page, port };
}

async function evalJs(page, expression, { awaitPromise = true, timeoutMs = 15000 } = {}) {
  const res = await Promise.race([
    page.send('Runtime.evaluate', { expression, awaitPromise, returnByValue: true, userGesture: true }),
    new Promise((_, rej) => setTimeout(() => rej(new Error('Runtime.evaluate 超时')), timeoutMs)),
  ]);
  if (res?.exceptionDetails) throw new Error('JS 异常: ' + (res.exceptionDetails.text || 'unknown') + ' ' + (res.exceptionDetails.exception?.description || ''));
  return res?.result?.value;
}
async function pageText(page) { return String(await evalJs(page, 'document.body ? document.body.innerText : ""')); }
async function waitForContent(page, ms = 60000) {
  const end = Date.now() + ms;
  let text = '';
  while (Date.now() < end) {
    try { text = await pageText(page); } catch { /* retry */ }
    if (text.trim().length > 50) return text;
    await sleep(1500);
  }
  return text;
}
async function waitReady(page, ms = 30000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { const s = await evalJs(page, 'document.readyState'); if (s === 'complete') return true; } catch { /* retry */ }
    await sleep(500);
  }
  return false;
}
async function shot(page, name) {
  const { data } = await page.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const file = path.join(recordDir, `${stamp()}-${name}.png`);
  fs.writeFileSync(file, Buffer.from(data, 'base64'));
  return file;
}
async function clickText(page, words) {
  const arr = JSON.stringify(words);
  const hit = await evalJs(page, `(() => {
    const words = ${arr};
    const nodes = [...document.querySelectorAll('button,a,label,span,div,li,p')];
    const matches = [];
    for (const el of nodes) {
      const t = (el.innerText || el.textContent || '').trim();
      if (!t) continue;
      if (!words.some((w) => t.includes(w))) continue;
      if (el.querySelector('button,a,input')) continue;
      el.scrollIntoView({ block: 'center' });
      const r = el.getBoundingClientRect();
      if (r.width < 4 || r.height < 4 || r.width > 520 || r.height > 220) continue;
      matches.push({ x: r.left + r.width / 2, y: r.top + r.height / 2, text: t.slice(0, 80), area: r.width * r.height, tag: el.tagName });
    }
    matches.sort((a, b) => a.area - b.area);
    return matches[0] || null;
  })()`);
  if (!hit) return null;
  try {
    await page.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: hit.x, y: hit.y });
    await page.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: hit.x, y: hit.y, button: 'left', clickCount: 1 });
    await page.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: hit.x, y: hit.y, button: 'left', clickCount: 1 });
  } catch { /* 坐标点击失败时忽略，仍返回命中文本 */ }
  return hit.text;
}
async function waitForText(page, words, timeoutMs) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const t = await pageText(page);
    if (words.some((w) => t.includes(w))) return true;
    await sleep(2000);
  }
  return false;
}
async function waitForInputs(page, count, timeoutMs = 30000) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const list = await listFileInputs(page);
    if (list.length >= count) return list;
    await sleep(1000);
  }
  return listFileInputs(page);
}
async function listFileInputs(page) {
  return await evalJs(page, `(() => [...document.querySelectorAll(${JSON.stringify(selectors.upload.fileInputSelector)})].map((el, i) => {
    const r = el.getBoundingClientRect();
    const box = (el.closest(${JSON.stringify(selectors.upload.slotContainerSelector)}) || el.parentElement || el).innerText || '';
    return { i, accept: el.accept || '', multiple: !!el.multiple, files: el.files ? el.files.length : 0,
             width: Math.round(r.width), height: Math.round(r.height), nearText: box.trim().slice(0, 60) };
  }))()`);
}
async function setFilesToInput(page, index, files) {
  const marked = await evalJs(page, `(() => {
    if (location.origin !== ${JSON.stringify(HUNYUAN_ORIGIN)}) return false;
    const el = document.querySelectorAll(${JSON.stringify(selectors.upload.fileInputSelector)})[${index}];
    if (!el) return false; el.setAttribute('data-dsh-hy', '${index}'); return true; })()`);
  const doc = await page.send('DOM.getDocument', { depth: 1 });
  if (!marked || !hunyuanPage(doc.root.documentURL)) stop(EXIT.UPLOAD, '上传目标不是混元 3D 页面');
  const { nodeId } = await page.send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: `input[data-dsh-hy="${index}"]` });
  if (!nodeId) throw new Error(`找不到第 ${index} 个 file input`);
  await page.send('DOM.setFileInputFiles', { nodeId, files: files.map((f) => path.resolve(f)) });
}
async function readQuota(page) {
  const text = await pageText(page);
  const keywords = anyText(selectors?.quota?.keywords, ['剩余', '次数', '积分', '生成次数']);
  const lines = text.split(/\r?\n/).map((s) => s.trim()).filter((s) => s && keywords.some((k) => s.includes(k)));
  let badge = null;
  try {
    badge = await evalJs(page, `(() => { const nodes = [...document.querySelectorAll(${JSON.stringify(selectors.quota.badgeSelector)})]; const values = [...new Set(nodes.map(el => el.textContent.trim()))]; return values.length === 1 ? values[0] : null; })()`);
  } catch { badge = null; }
  return { value: parseQuota(badge), badge, lines: [...new Set(lines)].slice(0, 20), raw: text.slice(0, 4000) };
}
async function isLoggedOut(page) {
  const text = await pageText(page);
  const outWords = anyText(selectors?.login?.loggedOutText, ['登录', '扫码登录', '微信登录', '手机号登录']);
  const inWords = anyText(selectors?.login?.loggedInText, ['退出', '个人中心', '我的账号']);
  return matchAny(text, outWords) && !matchAny(text, inWords);
}

// ---------- 业务动作 ----------
async function openCreation(page) {
  await page.send('Page.navigate', { url });
  await sleep(2000);
  await waitReady(page, 30000);
  await sleep(1500);
}
async function openMultiView(page) {
  const tabWords = anyText(selectors?.multiView?.tabTexts, ['多张图片']);
  const tabHit = await clickText(page, tabWords);
  if (tabHit) await sleep(1500);
  const openWords = anyText(selectors?.multiView?.openTexts, ['添加多视图', '多视图']);
  const openHit = await clickText(page, openWords);
  if (openHit) await sleep(2500);
  return { tab: tabHit, dialog: openHit };
}
async function applySettings(page, requested) {
  const wanted = requested || { modelVersion: selectors.settings.versionTexts[0], faces: 1500000 };
  const facesWords = wanted.faces === 1500000 ? selectors.settings.facesTexts : [String(wanted.faces)];
  if (!await clickText(page, [wanted.modelVersion]) || !await clickText(page, facesWords)) stop(EXIT.GEN_FAIL, '版本/面数控件点击失败；请 probe 校准');
  await sleep(500);
  const selected = await evalJs(page, `(() => [...document.querySelectorAll(${JSON.stringify(selectors.settings.selectedSelector)})].map(el => (el.innerText || el.textContent || el.value || '').trim()).filter(Boolean))()`);
  const versionValues = [...new Set(selected.flatMap(t => { const m = t.match(/^(?:3D生成\s*-\s*V|V)?(\d+\.\d+)$/i); return m ? [m[1]] : []; }))];
  const faceMap = { '1.5m': 1500000, '150万': 1500000, '1,500,000': 1500000, '1m': 1000000, '500k': 500000, '50k': 50000 };
  const faceValues = [...new Set(selected.flatMap(t => Object.entries(faceMap).filter(([word]) => t.toLowerCase() === word.toLowerCase()).map(([, n]) => n)))];
  const actual = { modelVersion: versionValues.length === 1 ? versionValues[0] : 'unknown', faces: faceValues.length === 1 ? faceValues[0] : 'unknown', generateType: 'unknown', selectedTexts: selected, webCapability: 'Normal (网页无类型选项；非DOM实测值)' };
  if (actual.modelVersion !== wanted.modelVersion || actual.faces !== wanted.faces) {
    writeJson(path.join(recordDir, 'settings-readback.json'), actual);
    stop(EXIT.GEN_FAIL, '配置回读失败/不匹配；实际值为 unknown 时禁止提交');
  }
  return actual;
}
async function slotState(page, view, index) {
  return evalJs(page, `(() => {
    const input = document.querySelectorAll(${JSON.stringify(selectors.upload.fileInputSelector)})[${index}];
    if (!input) return null;
    const root = input.closest(${JSON.stringify(selectors.upload.slotContainerSelector)});
    if (!root || root.querySelectorAll(${JSON.stringify(selectors.upload.fileInputSelector)}).length !== 1) return null;
    const text = root.innerText || '';
    const file = input.files?.[0]?.name || root.getAttribute('data-file-name') || '';
    const image = root.querySelector('img');
    const thumbnail = !!image && image.complete && image.naturalWidth > 0 && /^(blob:|https?:|data:)/.test(image.src || '');
    const uploading = /上传中|uploading|loading/i.test(text) || !!root.querySelector('[aria-busy=true], [role=progressbar], .uploading');
    const complete = !uploading && thumbnail && !/上传失败|upload failed|error/i.test(text);
    return {slot:${JSON.stringify(view.slot)}, file, thumbnail, uploading, complete, label: text.slice(0,120)};
  })()`);
}
async function waitSlot(page, view, index, timeoutMs = 180000) {
  const end = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < end) {
    const s = await slotState(page, view, index);
    last = s;
    if (s?.file === view.file && s.thumbnail && s.complete && !s.uploading) return s;
    await sleep(1000);
  }
  writeJson(path.join(recordDir, `upload-failed-${stamp()}.json`), { slot: view.slot, last, dryRun, screenshot: await shot(page, 'upload-failed') });
  stop(EXIT.UPLOAD, `槽位 ${view.slot} 的文件身份/缩略图/完成态未同时通过`);
}
async function uploadImages(page, images) {
  const inputs = await waitForInputs(page, selectors.upload.expectedInputs, 30000);
  if (inputs.length !== 8) stop(EXIT.UPLOAD, `file input 必须恰为8个，实测 ${inputs.length}`);
  const slots = [];
  for (let i = 0; i < 8; i++) {
    // 初始槽位标签是顺序身份的证据，文件上传完成后另核对文件名。
    if (!inputs[i].nearText.includes(VIEWS[i].label)) stop(EXIT.UPLOAD, `槽位标签不匹配：${VIEWS[i].slot}；请 probe 校准`);
    const before = await slotState(page, VIEWS[i], i);
    // A04：上传前已有缩略图说明可能复用旧图，无法证明是本次上传，直接拒绝。
    if (before?.thumbnail) stop(EXIT.UPLOAD, `槽位 ${VIEWS[i].slot} 上传前已有缩略图，拒绝把旧图当成本次上传`);
    await setFilesToInput(page, i, [images[i].path]);
    const s = await waitSlot(page, VIEWS[i], i);
    slots.push({ ...s, thumbnailUpdated: s.thumbnail === true && before?.thumbnail !== true });
  }
  const final = await Promise.all(VIEWS.map((v, i) => slotState(page, v, i)));
  // 把上传循环里已证明的“新缩略图”证据合并进最终回读，避免最终回读丢失证明。
  const merged = final.map((s, i) => (s ? { ...s, thumbnailUpdated: slots[i]?.thumbnailUpdated === true } : null));
  if (!uploadsComplete(merged)) stop(EXIT.UPLOAD, '最终逐槽回读失败，禁止提交');
  return merged;
}
async function submit(page) {
  if (!hunyuanPage(await evalJs(page, 'location.href'))) stop(EXIT.CONTEXT, '提交目标不是混元 3D 页面');
  const words = anyText(selectors?.submit?.texts, ['立即生成', '开始生成', '生成模型']);
  for (const w of words) { const hit = await clickText(page, [w]); if (hit) return hit; }
  stop(EXIT.GEN_FAIL, '没找到提交按钮；请 probe 校准');
}
async function readTaskContext(page, submittedAt) {
  const actual = await evalJs(page, String.raw`(() => {
    const u = new URL(location.href);
    let taskId = u.searchParams.get('taskId') || u.searchParams.get('task_id') || u.searchParams.get('id');
    if (!taskId) taskId = document.querySelector(${JSON.stringify(selectors.task.idSelector)})?.getAttribute('data-task-id');
    if (!taskId) { const m = u.pathname.match(/\/(?:task|result|detail)\/([^/]+)/i); taskId = m?.[1]; }
    return {taskId: taskId || null, resultPageUrl: u.href};
  })()`);
  if (!actual.taskId) return null;
  try { return checkedContext({ ...actual, submittedAt }); } catch { return null; }
}
async function assertCurrentTask(page, context) {
  const actual = await readTaskContext(page, context.submittedAt);
  if (!actual || actual.taskId !== context.taskId || actual.resultPageUrl !== context.resultPageUrl) stop(EXIT.CONTEXT, '当前结果页不属于已保存 taskId，禁止读完成态/下载');
}
async function pollResult(page, context) {
  const end = Date.now() + timeoutMin * 60000;
  let last = 'unknown';
  while (Date.now() < end) {
    await assertCurrentTask(page, context);
    const text = await pageText(page);
    if (/生成失败|任务失败|generation failed/i.test(text)) return { ok: false, status: 'failed' };
    const success = selectors.success.texts.find(w => text.includes(w));
    last = selectors.progress.texts.find(w => text.includes(w)) || success || 'unknown';
    log('task', context.taskId, 'status', last);
    if (success) return { ok: true, status: success };
    await sleep(intervalSec * 1000);
  }
  return { ok: false, status: last === 'unknown' ? 'unknown/timeout' : 'timeout' };
}
async function downloadResult(browser, page, context) {
  await assertCurrentTask(page, context);
  const final = path.join(outRoot, '初版.glb');
  guardTarget(final);
  fs.mkdirSync(outRoot, { recursive: true });
  const save = (buf, source, resource) => {
    const details = inspectGlb(buf);
    guardTarget(final);
    fs.writeFileSync(final, buf, { flag: force ? 'w' : 'wx' });
    const safeResource = resource ? new URL(resource).origin + new URL(resource).pathname : null;
    const updated = { ...context, ...details, file: path.basename(final), downloadedAt: new Date().toISOString(), downloadSource: source, modelResource: safeResource };
    writeJson(metadataPath, updated);
    return { file: final, ...details };
  };
  // ResourceTiming is limited to this task result document and resources loaded after submission.
  const resources = await evalJs(page, String.raw`(() => performance.getEntriesByType('resource').filter(e => /\.glb(\?|$)/i.test(e.name) && performance.timeOrigin + e.startTime >= ${Date.parse(context.submittedAt)}).map(e => ({url:e.name,at:performance.timeOrigin+e.startTime})))()`);
  const unique = [...new Map((resources || []).map(r => [r.url, r])).values()];
  if (unique.length === 1 && cdnResource(unique[0].url)) {
    const resource = unique[0].url;
    const res = await fetch(resource, { redirect: 'manual', signal: AbortSignal.timeout(180000) });
    if (res.ok) {
      const contents = Buffer.from(await res.arrayBuffer());
      await assertCurrentTask(page, context);
      return save(contents, 'task-resource', resource);
    }
    await res.body?.cancel();
  }
  // UI fallback accepts only a new download event from this task frame, never the largest old file.
  const dlDir = path.join(outRoot, `downloads-${stamp()}`);
  fs.mkdirSync(dlDir, { recursive: true });
  const frame = (await page.send('Page.getFrameTree')).frameTree.frame.id;
  const started = Date.now();
  let begun = null, completed = null;
  const offBegin = browser.on('Browser.downloadWillBegin', ev => { if (ev.frameId === frame && /\.glb$/i.test(ev.suggestedFilename || '') && Date.now() >= started) begun = ev; });
  const offProgress = browser.on('Browser.downloadProgress', ev => { if (begun && ev.guid === begun.guid && ev.state === 'completed') completed = ev; });
  try {
    await browser.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: dlDir, eventsEnabled: true });
    let clicked = false;
    for (const word of selectors.download.texts) { if (await clickText(page, [word])) { clicked = true; break; } }
    if (!clicked) stop(EXIT.GEN_FAIL, '本任务无可用GLB下载按钮');
    const end = Date.now() + 180000;
    while (Date.now() < end) {
      if (begun && completed) {
        const target = path.join(dlDir, path.basename(begun.suggestedFilename));
        if (fs.existsSync(target) && fs.statSync(target).mtimeMs >= started && fs.statSync(target).size === completed.receivedBytes) {
          await assertCurrentTask(page, context);
          return save(fs.readFileSync(target), 'task-download-event', null);
        }
      }
      await sleep(1000);
    }
    stop(EXIT.GEN_FAIL, '本任务GLB下载事件超时；不采用旧文件或zip');
  } finally { offBegin(); offProgress(); }
}

let liveConnections = null;
async function main() {
  if (!MODES.includes(mode)) stop(EXIT.USAGE, `未知 mode：${mode}；合法 mode：${MODES.join(', ')}`);
  if (flag('close') || flag('confirmed') || flag('confirm-before-submit')) stop(EXIT.USAGE, '已移除 --close/--confirmed/--confirm-before-submit；使用 upload 和 submit --confirm-file');
  if (!projectRoot) stop(EXIT.USAGE, '缺少 --project <项目根>');
  if (!hunyuanPage(url)) stop(EXIT.USAGE, '--url 必须指向混元 3D 的 HTTPS 页面');
  // All submit confirmation failures are resolved before browser discovery or any fetch.
  const confirmation = mode === 'submit' ? loadConfirmation() : null;
  selectors = readJson(selectorsPath, null);
  if (!selectors?.upload || !selectors?.settings || !selectors?.task) stop(EXIT.ERROR, '选择器配置缺失/无效');
  let images = null;
  if (mode === 'upload' || mode === 'submit') {
    if (mode === 'submit') {
      const version = path.relative(viewsRoot, imagesDir);
      if (!/^v[1-9]\d*$/.test(version) || !fs.existsSync(imagesDir) || fs.realpathSync(imagesDir) !== imagesDir) {
        stop(EXIT.CONFIRM, 'submit 仅接受本项目 3.图片/vN 的实际版本目录');
      }
    }
    try { images = inspectImages(); } catch (e) { if (mode === 'submit') e.exitCode = EXIT.CONFIRM; throw e; }
  }
  if (confirmation) {
    validateConfirmation(confirmation.c, { project: projectRoot, imageSha256: images.map(x => x.sha256), modelVersion: confirmation.c.modelVersion, faces: confirmation.c.faces, generateType: 'Normal' });
    confirmation.hash = confirmationDigest(confirmation.c);
    const confirmationDir = path.dirname(confirmation.file);
    confirmation.receipt = path.join(confirmationDir, `submit-used-${confirmation.hash}.json`);
    if (fs.existsSync(confirmation.receipt) || previouslyAttempted(confirmationDir, confirmation.c.confirmedAt)) stop(EXIT.CONFIRM, '该确认已用于提交尝试；先 status/download 恢复，不得重复消耗');
    guardTarget(metadataPath); guardTarget(path.join(outRoot, '初版.glb'));
  }
  const savedContext = mode === 'status' || mode === 'download' ? checkedContext(readJson(metadataPath, null)) : null;
  if (mode === 'download') guardTarget(path.join(outRoot, '初版.glb'));
  if (!Number.isFinite(timeoutMin) || timeoutMin <= 0 || !Number.isFinite(intervalSec) || intervalSec <= 0) stop(EXIT.USAGE, 'timeout-min/interval-sec 必须为正数');
  fs.mkdirSync(recordDir, { recursive: true });
  const { port, exe } = await ensureBrowser(savedContext?.resultPageUrl || url);
  const { browser, page } = await connectBrowser(port);
  liveConnections = { browser, page };
  const statePath = path.join(recordDir, 'state.json');
  writeJson(statePath, { mode, startedAt: new Date().toISOString(), url, browser: exe, port, profileDir });

  if (savedContext) {
    await page.send('Page.navigate', { url: savedContext.resultPageUrl });
    await waitReady(page);
  } else if (mode === 'wait-login') {
    try {
      const href = await evalJs(page, 'location.href');
      if (!/hunyuan/i.test(String(href))) await openCreation(page);
    } catch { await openCreation(page); }
    await sleep(1500);
  } else {
    await openCreation(page);
    await sleep(1500);
  }

  const priorTask = mode === 'submit' ? await readTaskContext(page, new Date().toISOString()) : null;

  if (mode === 'wait-login') {
    await waitForContent(page, 60000);
    const end = Date.now() + timeoutMin * 60 * 1000;
    while (Date.now() < end) {
      const text = await pageText(page);
      if (text.trim().length > 50 && !(await isLoggedOut(page))) {
        const s = await shot(page, 'login-detected');
        writeJson(path.join(recordDir, 'login-detected.json'), { at: new Date().toISOString(), screenshot: s, text: text.slice(0, 3000) });
        console.log(JSON.stringify({ ok: true, mode, login: true, screenshot: s, textLength: text.length }));
        return EXIT.OK;
      }
      await sleep(5000);
    }
    const s = await shot(page, 'login-timeout');
    writeJson(path.join(recordDir, 'login-timeout.json'), { at: new Date().toISOString(), screenshot: s, text: (await pageText(page)).slice(0, 1000) });
    console.log(JSON.stringify({ ok: false, mode, login: false, screenshot: s }));
    return EXIT.LOGIN;
  }

  if (mode === 'probe') {
    await waitForContent(page, 60000);
    let dialogHit = null;
    try { const mv = await openMultiView(page); dialogHit = mv.dialog || mv.tab; await sleep(2500); } catch { dialogHit = null; }
    const probeDir = path.join(recordDir, `probe-${stamp()}`);
    fs.mkdirSync(probeDir, { recursive: true });
    const html = await evalJs(page, 'document.documentElement.outerHTML');
    fs.writeFileSync(path.join(probeDir, 'page.html'), html, 'utf8');
    const text = await pageText(page);
    fs.writeFileSync(path.join(probeDir, 'page.txt'), text, 'utf8');
    const inputs = await listFileInputs(page);
    writeJson(path.join(probeDir, 'inputs.json'), inputs);
    const buttons = await evalJs(page, `(() => [...document.querySelectorAll('button,a,div[role=button],label,span,li')]
      .map((el) => ({ tag: el.tagName, text: (el.innerText || el.textContent || '').trim().slice(0, 80),
        w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height) }))
      .filter((x) => x.text && x.w > 0 && x.h > 0).slice(0, 400))()`);
    writeJson(path.join(probeDir, 'buttons.json'), buttons);
    const badges = await evalJs(page, `(() => {
      const out = [];
      document.querySelectorAll('*').forEach((el) => {
        const t = (el.textContent || '').trim();
        const r = el.getBoundingClientRect();
        if (/^\\d+$/.test(t) && t.length <= 3 && r.width > 0 && r.height > 0 && el.children.length === 0) {
          out.push({ tag: el.tagName, text: t, cls: String(el.className || '').slice(0, 80),
            title: el.title || '', aria: el.getAttribute('aria-label') || '',
            html: el.outerHTML.slice(0, 300),
            parentHtml: (el.parentElement ? el.parentElement.outerHTML : '').slice(0, 600) });
        }
      });
      return out.slice(0, 40);
    })()`);
    writeJson(path.join(probeDir, 'badges.json'), badges);
    writeJson(path.join(probeDir, 'quota.json'), await readQuota(page));
    fs.writeFileSync(path.join(probeDir, 'screenshot.png'), Buffer.from((await page.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
    console.log(JSON.stringify({ ok: true, mode, probeDir, dialog: dialogHit, loggedOut: await isLoggedOut(page), inputs: inputs.length }));
    return EXIT.OK;
  }

  await waitForContent(page, 60000);
  if (await isLoggedOut(page)) {
    const s = await shot(page, 'login-required');
    writeJson(path.join(recordDir, 'interact-required.json'), { type: 'login', screenshot: s, at: new Date().toISOString() });
    console.log(JSON.stringify({ ok: false, code: 'LOGIN_REQUIRED', message: '请在打开的浏览器窗口完成登录后重跑', screenshot: s }));
    return EXIT.LOGIN;
  }

  const quota = await readQuota(page);
  writeJson(path.join(recordDir, 'quota.json'), quota);
  log('额度DOM原文', JSON.stringify(quota));

  if (mode === 'status') {
    await assertCurrentTask(page, savedContext);
    const screenshot = await shot(page, 'status');
    writeJson(path.join(recordDir, `status-${stamp()}.json`), { taskId: savedContext.taskId, at: new Date().toISOString(), quota, text: (await pageText(page)).slice(0, 3000), screenshot });
    console.log(JSON.stringify({ ok: true, mode, taskId: savedContext.taskId, screenshot }));
    return EXIT.OK;
  }
  if (mode === 'download') {
    const result = await pollResult(page, savedContext);
    if (!result.ok) stop(EXIT.GEN_FAIL, `本任务未完成：${result.status}`);
    console.log(JSON.stringify({ ok: true, mode, ...await downloadResult(browser, page, { ...savedContext, quota, taskStatus: result.status }) }));
    return EXIT.OK;
  }

  await openMultiView(page);
  const slots = await uploadImages(page, images);
  const settings = await applySettings(page, confirmation?.c);
  const screenshot = await shot(page, 'before-submit');
  const pending = { at: new Date().toISOString(), quota, images, imageSha256: images.map(x => x.sha256), settings, slots, screenshot, mode, url, dryRun, evidence: '逐槽文件名+已解码缩略图+无上传中；未使用全页img数量' };
  writeJson(path.join(recordDir, 'pending-confirm.json'), pending);
  if (mode === 'upload' || dryRun) {
    console.log(JSON.stringify({ ok: true, mode, dryRun: true, pending: path.join(recordDir, 'pending-confirm.json'), quota, screenshot, message: '未点击提交。用户确认后建立确认文件，再显式 --mode submit。' }));
    return EXIT.OK;
  }
  // A02: refresh the quota immediately before a consuming click.
  const quotaNow = await readQuota(page);
  writeJson(path.join(recordDir, 'quota.json'), quotaNow);
  log('提交前额度DOM原文', JSON.stringify(quotaNow));
  if (quotaNow.value === null || quotaNow.value < 1) {
    writeJson(metadataPath, { source: 'hunyuan-web', project: projectRoot, submissionAttempted: false, taskStatus: 'blocked-quota', quota: quotaNow, ...settings });
    stop(EXIT.QUOTA, '提交前额度未知或不足1，禁止提交');
  }
  validateSubmitQuota(quotaNow.value, confirmation.c.quotaBefore);
  const currentImages = inspectImages();
  validateConfirmation(confirmation.c, { project: projectRoot, imageSha256: currentImages.map(x => x.sha256), modelVersion: settings.modelVersion, faces: settings.faces, generateType: 'Normal' });
  if (!uploadsComplete(await Promise.all(VIEWS.map((v, i) => slotState(page, v, i))))) stop(EXIT.UPLOAD, '提交前逐槽状态变化，禁止提交');
  guardTarget(path.join(outRoot, '初版.glb'));
  const submittedAt = new Date().toISOString();
  // Exclusive local receipt prevents the same confirmation from being consumed twice, including after a timeout.
  fs.writeFileSync(confirmation.receipt, JSON.stringify({ submittedAt, confirmationSha256: confirmation.hash, project: projectRoot }), { flag: 'wx' });
  let context = { source: 'hunyuan-web', project: projectRoot, taskId: null, resultPageUrl: null, submittedAt, submissionAttempted: true, confirmationSha256: confirmation.hash, imageSha256: currentImages.map(x => x.sha256), ...settings, quota: quotaNow, taskStatus: 'submission-attempted' };
  writeJson(metadataPath, context);
  await submit(page);
  const identityEnd = Date.now() + 60000;
  while (Date.now() < identityEnd) {
    const task = await readTaskContext(page, submittedAt);
    if (task && task.taskId !== priorTask?.taskId) { context = { ...context, ...task }; break; }
    await sleep(1000);
  }
  writeJson(metadataPath, context);
  checkedContext(context);
  const result = await pollResult(page, context);
  context.taskStatus = result.status;
  writeJson(metadataPath, context);
  if (!result.ok) stop(EXIT.GEN_FAIL, `本任务生成失败或超时：${result.status}；仅用 status/download 恢复，禁止自动新提交`);
  const dl = await downloadResult(browser, page, context);
  console.log(JSON.stringify({ ok: true, mode, taskId: context.taskId, ...dl }));
  return EXIT.OK;
}

// Importing this module exposes pure offline checks; browser and filesystem mutations are CLI-only.
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let exitCode = EXIT.ERROR;
  try { exitCode = await main(); }
  catch (err) {
    log('ERROR', err?.message || String(err));
    exitCode = err?.exitCode ?? (err?.code === 'NEED_BROWSER' ? EXIT.NEED_BROWSER : EXIT.ERROR);
  } finally {
    liveConnections?.page.close(); liveConnections?.browser.close();
  }
  process.exit(exitCode);
}
