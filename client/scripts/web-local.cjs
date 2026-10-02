// Explicit loopback settings; keep local startup independent of personal env files.
const { spawn } = require('node:child_process');
const build = process.argv.includes('--export');
const extraArgs = process.argv.slice(2).filter((arg) => arg !== '--export');
const hasHostOption = extraArgs.some((arg) => ['--offline', '--host', '--localhost', '--lan', '--tunnel'].includes(arg) || arg.startsWith('--host='));
const hostArgs = hasHostOption ? [] : ['--host', 'localhost'];
const command = build ? ['export', '--platform', 'web'] : ['start', '--web', '--port', '8081', ...hostArgs];
const child = spawn(process.execPath, [require.resolve('expo/bin/cli'), ...command, ...extraArgs], {
  stdio: 'inherit',
  env: {
    ...process.env,
    EXPO_NO_DOTENV: '1',
    EXPO_PUBLIC_API_URL: 'http://127.0.0.1:8000',
    EXPO_PUBLIC_API_USER: 'local',
    EXPO_PUBLIC_API_PASS: 'local',
  },
});
child.on('exit', (code) => { process.exitCode = code ?? 1; });
