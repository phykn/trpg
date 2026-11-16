// `npm run serve`: the local API behind a quick tunnel whose URL the Worker reads from KV, with watchers that restart
// the API when the server or a story changes and redeploy the page when the client changes. Its state goes to
// logs/serve.json for the Mac app.
const { spawn, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { checkApi, root, sleep, spawnApi, waitForApi } = require('./common.cjs');
const { tunnelBinary } = require('./tunnel.cjs');

const client = path.join(root, 'client');
const wrangler = path.join(client, 'node_modules/wrangler/bin/wrangler.js');
const statePath = path.join(root, 'logs/serve.json');
const state = { ready: false, address: null, deploying: false, error: null };
const children = [];
let stopping = false;
let published = false;   // KV points at this run's tunnel
let api = null;
let deploying = false;
let deployAgain = false;

function report(change) {
  Object.assign(state, change);
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  fs.writeFileSync(`${statePath}.tmp`, JSON.stringify(state));
  fs.renameSync(`${statePath}.tmp`, statePath);
}

function kv(...args) {
  const { status } = spawnSync(process.execPath, [wrangler, 'kv', 'key', ...args, '--binding', 'TUNNEL', '--remote'],
    { cwd: client, stdio: ['ignore', 'ignore', 'inherit'] });
  return status === 0;
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM');
  // Without this the Worker keeps forwarding to a dead tunnel until KV is overwritten. A run that never published
  // leaves KV alone: it may belong to another serve that is still running.
  if (published) kv('delete', 'origin');
  console.log('서버를 내렸습니다.');
  process.exit(code);
}

function track(child, name) {
  children.push(child);
  child.on('error', (error) => fail(new Error(`${name}: ${error.message}`)));
  return child;
}

function fail(error) {
  console.error(error.message);
  report({ error: error.message });
  stop(1);
}

function startApi() {
  const self = track(spawnApi(), 'api');
  self.on('exit', () => { if (!stopping && api === self) console.error('API가 멈췄습니다. 코드를 고치면 다시 시작합니다.'); });
  api = self;
  return self;
}

// Only the API restarts; the tunnel and its KV entry stay, so the address keeps working.
function restartApi() {
  const old = api;
  api = null;
  const start = () => {
    if (stopping) return;
    console.log('\n코드가 바뀌어 API를 다시 시작합니다.');
    startApi();
  };
  if (old && old.exitCode === null && old.signalCode === null) {
    old.once('exit', start);
    old.kill('SIGTERM');
  } else start();
}

function watch(dir, accept, act, ms) {
  let timer = null;
  fs.watch(path.join(root, dir), { recursive: true }, (_, file) => {
    if (!file || !accept(file)) return;
    clearTimeout(timer);
    timer = setTimeout(act, ms);
  });
}

// One build at a time; edits made during a build trigger exactly one more.
function deployClient(reason = '화면 코드가 바뀌어 배포합니다') {
  if (stopping) return;
  if (deploying) {
    deployAgain = true;
    return;
  }
  deploying = true;
  report({ deploying: true });
  console.log(`\n${reason} (1분쯤).`);
  let log = '';
  const child = track(spawn(process.execPath, [path.join(__dirname, 'deploy.cjs')], { cwd: client, stdio: ['ignore', 'pipe', 'pipe'] }), 'deploy');
  child.stdout.on('data', (chunk) => { log += chunk; });
  child.stderr.on('data', (chunk) => { log += chunk; });
  child.on('exit', (code) => {
    deploying = false;
    if (stopping) return;
    if (code === 0) console.log('화면 배포 완료. 새로고침하면 반영됩니다.');
    else console.error(`화면 배포 실패:\n${log.trim().split('\n').slice(-15).join('\n')}`);
    if (deployAgain) {
      deployAgain = false;
      deployClient();
    } else report({ deploying: false });
  });
}

// Each run of a quick tunnel gets a new URL, so a dropped tunnel is replaced and KV rewritten.
async function runTunnel(binary) {
  while (!stopping) {
    const tunnel = track(spawn(binary, ['tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:8000'], { stdio: ['ignore', 'ignore', 'pipe'] }), 'cloudflared');
    const url = await new Promise((resolve) => {
      let log = '';
      tunnel.stderr.on('data', (chunk) => {
        log += chunk;
        const match = log.match(/https:\/\/[a-z0-9-]+\.trycloudflare\.com/);
        if (match) resolve(match[0]);
      });
      tunnel.on('exit', () => resolve(null));
    });
    if (url) {
      let up = false;
      for (let attempt = 0; attempt < 60 && !up && tunnel.exitCode === null; attempt++) {
        up = await checkApi(url, 5000) === 'engine';
        if (!up) await sleep(2000);
      }
      if (up && kv('put', 'origin', url)) {
        published = true;
        console.log(`\n외부 접속 준비 완료: ${state.address ?? '배포한 workers.dev 주소'} (1분쯤 뒤부터)\n터널: ${url}\n코드를 바꾸면 알아서 반영합니다: 서버·스토리는 API 재시작, 화면은 자동 배포(1분쯤).\n종료: Ctrl+C\n`);
        report({ ready: true });
      } else {
        console.error('터널이 응답하지 않아 다시 엽니다.');
        tunnel.kill('SIGTERM');
      }
    }
    if (tunnel.exitCode === null) await new Promise((resolve) => tunnel.on('exit', resolve));
    if (!stopping) {
      console.error('터널이 끊겨 다시 엽니다.');
      await sleep(2000);
    }
  }
}

// The Worker's address comes from the account's workers.dev subdomain at run time; the repository never holds it.
async function findWorkerAddress() {
  try {
    const json = (...args) => JSON.parse(spawnSync(process.execPath, [wrangler, ...args, '--json'],
      { cwd: client, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).stdout);
    const account = json('whoami').accounts[0].id;
    const { token } = json('auth', 'token');
    const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${account}/workers/subdomain`,
      { headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(10000) });
    const { subdomain } = (await response.json()).result;
    const config = fs.readFileSync(path.join(client, 'wrangler.jsonc'), 'utf8').replace(/^\s*\/\/.*$/gm, '');
    return `https://${JSON.parse(config).name}.${subdomain}.workers.dev`;
  } catch {
    return null;
  }
}

async function main() {
  report({});
  report({ address: await findWorkerAddress() });
  if (process.platform === 'darwin') track(spawn('caffeinate', ['-i', '-w', String(process.pid)], { stdio: 'ignore' }), 'caffeinate');
  const binary = await tunnelBinary();
  if (await checkApi() === 'engine') {
    throw new Error('Port 8000 already has an API. Stop it so serve can restart its own API on code changes.');
  }
  await waitForApi(startApi());
  watch('server', (file) => file.endsWith('.py') && !file.includes('__pycache__') && !file.startsWith('tests'), restartApi, 500);
  watch('scenarios', (file) => file.endsWith('.yaml'), restartApi, 500);
  const skipped = ['node_modules', 'dist', '.expo', '.wrangler', '__tests__', 'scripts'];
  watch('client', (file) => !skipped.some((dir) => file.split(path.sep).includes(dir))
    && /\.(tsx?|jsx?|cjs|css|json|jsonc|png|ttf)$/.test(file) && !file.startsWith('package-lock'), () => deployClient(), 2000);
  deployClient('최신 화면을 배포합니다');
  await runTunnel(binary);
}

process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
main().catch(fail);
