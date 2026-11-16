const { spawn } = require('node:child_process');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const apiBase = 'http://127.0.0.1:8000';
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Explicit local settings, so local startup never depends on personal env files.
const localEnv = (url) => ({
  ...process.env,
  EXPO_NO_DOTENV: '1',
  EXPO_PUBLIC_API_URL: url,
  EXPO_PUBLIC_API_USER: 'local',
  EXPO_PUBLIC_API_PASS: 'local',
});

// 'engine' for this game's API, 'refused' when nothing listens, 'other' for anything else.
async function checkApi(base = apiBase, ms = 1000) {
  try {
    const response = await fetch(`${base}/health`, { signal: AbortSignal.timeout(ms) });
    return response.ok && (await response.json()).ok === true ? 'engine' : 'other';
  } catch (error) {
    return error.cause?.code === 'ECONNREFUSED' ? 'refused' : 'other';
  }
}

// `run_api.py --local`, its error output passed through and its last line kept: on a failed start it says why.
function spawnApi() {
  const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const api = spawn(python, ['server/run_api.py', '--local'], { cwd: root, stdio: ['ignore', 'inherit', 'pipe'] });
  api.lastLine = '';
  api.stderr.on('data', (chunk) => {
    process.stderr.write(chunk);
    api.lastLine = String(chunk).split('\n').filter((line) => line.trim()).at(-1) ?? api.lastLine;
  });
  return api;
}

// Startup checks every story and both models and warms the narrator, which can take a minute.
async function waitForApi(api) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (api.exitCode !== null || api.signalCode !== null) throw new Error(api.lastLine || 'The API stopped while starting.');
    if (await checkApi() === 'engine') return;
    await sleep(1000);
  }
  throw new Error('API startup timed out. Check the server output.');
}

module.exports = { root, sleep, localEnv, checkApi, spawnApi, waitForApi };
