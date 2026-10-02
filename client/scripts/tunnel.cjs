const { createHash } = require('node:crypto');
const { mkdir, readFile, writeFile } = require('node:fs/promises');
const path = require('node:path');

async function tunnelBinary() {
  if (process.platform !== 'win32' || process.arch !== 'x64') return 'cloudflared';
  const dir = path.resolve(__dirname, '../node_modules/.cache/cloudflared');
  const file = path.join(dir, '2026.9.3.exe');
  let bytes;
  try { bytes = await readFile(file); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    console.log('Cloudflare 공식 터널 도구를 다운로드합니다. 최초 실행 시 한 번 필요합니다.');
    const response = await fetch('https://github.com/cloudflare/cloudflared/releases/download/2026.9.3/cloudflared-windows-amd64.exe', { signal: AbortSignal.timeout(120_000) });
    if (!response.ok) throw new Error(`cloudflared download failed: HTTP ${response.status}`);
    bytes = Buffer.from(await response.arrayBuffer());
  }
  const digest = createHash('sha256').update(bytes).digest('hex');
  if (digest !== 'f096265ec2fcbe9bb6e2d64268db167ced3fcbb83d894bdb9e2fcdb26f2ea7e2') {
    throw new Error(`cloudflared checksum mismatch. Remove ${file} and retry.`);
  }
  await mkdir(dir, { recursive: true });
  await writeFile(file, bytes);
  return file;
}

module.exports = { tunnelBinary };
