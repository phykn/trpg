const { spawnSync } = require('node:child_process');
const { existsSync, readFileSync, readdirSync, rmSync } = require('node:fs');
const { join } = require('node:path');

function loadEnvFile(path) {
  if (!existsSync(path)) {
    throw new Error(`${path} is missing`);
  }

  for (const rawLine of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const index = line.indexOf('=');
    if (index < 1) continue;

    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function verifyExportedEnv() {
  const jsDir = join(__dirname, '..', 'dist', '_expo', 'static', 'js', 'web');
  const entry = readdirSync(jsDir).find((name) => /^entry-.*\.js$/.test(name));
  if (!entry) {
    throw new Error('Expo export is missing the web entry bundle');
  }

  const source = readFileSync(join(jsDir, entry), 'utf8');
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  if (!source.includes(apiUrl)) {
    throw new Error('Expo export did not inline EXPO_PUBLIC_API_URL');
  }
  if (source.includes('EXPO_PUBLIC_API_URL is not set')) {
    throw new Error('Expo export contains a missing EXPO_PUBLIC_API_URL guard');
  }
}

const isWindows = process.platform === 'win32';
const npx = isWindows ? 'npx.cmd' : 'npx';
const wrangler = isWindows ? 'wrangler.cmd' : 'wrangler';

loadEnvFile(join(__dirname, '..', '.env.release'));

const sha = spawnSync('git', ['rev-parse', '--short', 'HEAD'], {
  encoding: 'utf8',
  shell: false,
});
if (sha.error) throw sha.error;
if (sha.status !== 0) process.exit(sha.status ?? 1);
process.env.EXPO_PUBLIC_GIT_SHA = sha.stdout.trim();

rmSync(join(__dirname, '..', 'dist'), { recursive: true, force: true });
run(npx, ['expo', 'export', '-p', 'web', '--clear']);
verifyExportedEnv();
run(wrangler, ['deploy']);
