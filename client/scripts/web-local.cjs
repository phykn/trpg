// `npm run web` and `npm run build:web`: Expo against the local API, whatever the personal env files say.
const { spawn } = require('node:child_process');
const { localEnv } = require('./common.cjs');

const build = process.argv.includes('--export');
const extra = process.argv.slice(2).filter((arg) => arg !== '--export');
const hosted = extra.some((arg) => ['--offline', '--host', '--localhost', '--lan', '--tunnel'].includes(arg) || arg.startsWith('--host='));
const command = build ? ['export', '--platform', 'web'] : ['start', '--web', '--port', '8090', ...(hosted ? [] : ['--host', 'localhost'])];
const child = spawn(process.execPath, [require.resolve('expo/bin/cli'), ...command, ...extra], {
  stdio: 'inherit',
  env: localEnv('http://127.0.0.1:8000'),
});
child.on('exit', (code) => { process.exitCode = code ?? 1; });
