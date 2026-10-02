const { spawn, spawnSync } = require('node:child_process');
const { networkInterfaces } = require('node:os');
const { createConnection } = require('node:net');
const path = require('node:path');
const { tunnelBinary } = require('./tunnel.cjs');

const root = path.resolve(__dirname, '../..');
const children = [];
let stopping = false;

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.pid || child.exitCode !== null) continue;
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    } else child.kill('SIGTERM');
  }
  process.exit(code);
}

function start(command, args, cwd, env = process.env) {
  const child = spawn(command, args, { cwd, env, stdio: 'inherit' });
  children.push(child);
  child.on('error', (error) => { console.error(error.message); stop(1); });
  child.on('exit', (code) => stop(code ?? 1));
  return child;
}

async function apiRunning() {
  try {
    const response = await fetch('http://127.0.0.1:8000/health', { signal: AbortSignal.timeout(1000) });
    if (!response.ok || (await response.json()).mode !== 'adventure') {
      throw new Error('Port 8000 is occupied by a different service.');
    }
    return true;
  } catch (error) {
    if (error.cause?.code === 'ECONNREFUSED') return false;
    throw error;
  }
}

async function main() {
  await new Promise((resolve, reject) => {
    const socket = createConnection({ host: '127.0.0.1', port: 8081 });
    socket.once('connect', () => {
      socket.destroy();
      reject(new Error('Port 8081 is already in use. Stop the previous web command first.'));
    });
    socket.once('error', (error) => error.code === 'ECONNREFUSED' ? resolve() : reject(error));
  });
  const publicAccess = process.argv.includes('--public');
  const tunnel = publicAccess ? await tunnelBinary() : null;
  if (await apiRunning()) console.log('기존 모험 API를 사용합니다.');
  else {
    const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    start(python, ['server/run_api.py', '--local'], root);
    let ready = false;
    for (let attempt = 0; attempt < 20; attempt++) {
      if (await apiRunning()) { ready = true; break; }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!ready) throw new Error('API startup timed out. Check the server output.');
  }
  console.log('\n휴대폰 접속 주소:');
  for (const addresses of Object.values(networkInterfaces())) {
    for (const address of addresses ?? []) {
      if (address.family === 'IPv4' && !address.internal) console.log(`  http://${address.address}:8081`);
    }
  }
  console.log('  PC: http://localhost:8081\n');
  start(process.execPath, [require.resolve('expo/bin/cli'), 'start', '--web', '--host', 'lan', '--port', '8081', ...process.argv.slice(2).filter((arg) => arg !== '--public')], path.join(root, 'client'), {
    ...process.env,
    EXPO_NO_DOTENV: '1',
    EXPO_PUBLIC_API_URL: '/api',
    EXPO_PUBLIC_API_USER: 'local',
    EXPO_PUBLIC_API_PASS: 'local',
    TRPG_DEV_PROXY: '1',
  });
  if (tunnel) {
    console.log('LTE 접속: 아래에 표시되는 https://…trycloudflare.com 주소를 엽니다.');
    start(tunnel, ['tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:8081'], root);
  }
}

process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
main().catch((error) => { console.error(error.message); stop(1); });
