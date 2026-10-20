// Opens the Mac API to the deployed Worker: API, quick tunnel, and the tunnel URL in KV.
const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');
const { tunnelBinary } = require('./tunnel.cjs');

const root = path.resolve(__dirname, '../..');
const client = path.join(root, 'client');
const wrangler = path.join(__dirname, '../node_modules/wrangler/bin/wrangler.js');
const children = [];
let stopping = false;

function kv(...args) {
  const { status } = spawnSync(process.execPath, [wrangler, 'kv', 'key', ...args, '--binding', 'TUNNEL', '--remote'],
    { cwd: client, stdio: ['ignore', 'ignore', 'inherit'] });
  return status === 0;
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) child.kill('SIGTERM');
  // Without this the Worker keeps proxying to a dead tunnel until KV is overwritten.
  kv('delete', 'origin');
  console.log('서버를 내렸습니다.');
  process.exit(code);
}

function track(child, name) {
  children.push(child);
  child.on('error', (error) => { console.error(`${name}: ${error.message}`); stop(1); });
  return child;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function healthy(base) {
  try {
    const response = await fetch(`${base}/health`, { signal: AbortSignal.timeout(5000) });
    return response.ok && (await response.json()).mode === 'engine';
  } catch {
    return false;
  }
}

async function startApi() {
  if (await healthy('http://127.0.0.1:8000')) return console.log('기존 게임 API를 사용합니다.');
  const api = track(spawn(path.join(root, '.venv/bin/python'), ['server/run_api.py', '--local'], { cwd: root, stdio: 'inherit' }), 'api');
  api.on('exit', (code) => { if (!stopping) { console.error('API가 종료되었습니다.'); stop(code ?? 1); } });
  for (let attempt = 0; attempt < 60; attempt++) {
    if (await healthy('http://127.0.0.1:8000')) return;
    await sleep(500);
  }
  throw new Error('API startup timed out. Check the server output.');
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
      let ready = false;
      for (let attempt = 0; attempt < 60 && !ready && tunnel.exitCode === null; attempt++) {
        ready = await healthy(url);
        if (!ready) await sleep(2000);
      }
      if (ready && kv('put', 'origin', url)) {
        console.log(`\n외부 접속 준비 완료: 배포한 workers.dev 주소 (1분쯤 뒤부터)\n터널: ${url}\n종료: Ctrl+C\n`);
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

async function main() {
  if (process.platform === 'darwin') track(spawn('caffeinate', ['-i', '-w', String(process.pid)], { stdio: 'ignore' }), 'caffeinate');
  const binary = await tunnelBinary();
  await startApi();
  await runTunnel(binary);
}

process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
main().catch((error) => { console.error(error.message); stop(1); });
