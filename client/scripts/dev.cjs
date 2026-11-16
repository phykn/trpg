// `npm run dev`: the web on the local network (port 8090) with /api forwarded to the local API, started here if none
// runs; `--public` adds a temporary public HTTPS address through a quick tunnel.
const { spawn, spawnSync } = require('node:child_process');
const { createConnection } = require('node:net');
const { networkInterfaces } = require('node:os');
const path = require('node:path');
const { checkApi, localEnv, root, spawnApi, waitForApi } = require('./common.cjs');
const { tunnelBinary } = require('./tunnel.cjs');

const children = [];
let stopping = false;

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.pid || child.exitCode !== null) continue;
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else child.kill('SIGTERM');
  }
  process.exit(code);
}

// Whichever child stops, everything stops.
function track(child) {
  children.push(child);
  child.on('error', (error) => { console.error(error.message); stop(1); });
  child.on('exit', (code) => stop(code ?? 1));
  return child;
}

async function main() {
  await new Promise((resolve, reject) => {
    const socket = createConnection({ host: '127.0.0.1', port: 8090 });
    socket.once('connect', () => {
      socket.destroy();
      reject(new Error('Port 8090 is already in use. Stop the previous web command first.'));
    });
    socket.once('error', (error) => (error.code === 'ECONNREFUSED' ? resolve() : reject(error)));
  });
  const tunnel = process.argv.includes('--public') ? await tunnelBinary() : null;
  const api = await checkApi();
  if (api === 'other') throw new Error('Port 8000 is occupied by a different service.');
  if (api === 'engine') console.log('기존 게임 API를 사용합니다.');
  else await waitForApi(track(spawnApi()));

  console.log('\n휴대폰 접속 주소:');
  for (const address of Object.values(networkInterfaces()).flat()) {
    if (address?.family === 'IPv4' && !address.internal) console.log(`  http://${address.address}:8090`);
  }
  console.log('  PC: http://localhost:8090\n');
  const expo = [require.resolve('expo/bin/cli'), 'start', '--web', '--host', 'lan', '--port', '8090',
    ...process.argv.slice(2).filter((arg) => arg !== '--public')];
  track(spawn(process.execPath, expo, { cwd: path.join(root, 'client'), env: { ...localEnv('/api'), TRPG_DEV_PROXY: '1' }, stdio: 'inherit' }));
  if (tunnel) {
    console.log('LTE 접속: 아래에 표시되는 https://…trycloudflare.com 주소를 엽니다.');
    track(spawn(tunnel, ['tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:8090'], { cwd: root, stdio: 'inherit' }));
  }
}

process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
main().catch((error) => { console.error(error.message); stop(1); });
