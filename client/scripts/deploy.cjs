// Builds the web client against the Worker's /api proxy and publishes it to workers.dev.
// --clear: Metro caches inlined EXPO_PUBLIC_* values from the last local build.
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const client = path.resolve(__dirname, '..');
const env = {
  ...process.env,
  EXPO_NO_DOTENV: '1',
  EXPO_PUBLIC_API_URL: '/api',
  EXPO_PUBLIC_API_USER: 'local',
  EXPO_PUBLIC_API_PASS: 'local',
};
for (const args of [[require.resolve('expo/bin/cli'), 'export', '--platform', 'web', '--clear'], [path.join(__dirname, '../node_modules/wrangler/bin/wrangler.js'), 'deploy']]) {
  const { status } = spawnSync(process.execPath, args, { cwd: client, env, stdio: 'inherit' });
  if (status !== 0) process.exit(status ?? 1);
}
