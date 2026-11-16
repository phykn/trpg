import fs from 'fs';
import path from 'path';

const root = path.resolve(__dirname, '..', '..');
const skipped = ['__tests__', 'node_modules', '.expo', 'dist'];

function listSources(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return skipped.includes(entry.name) ? [] : listSources(full);
    return /\.tsx?$/.test(entry.name) && full !== path.join(root, 'locale', 'ko.ts') ? [full] : [];
  });
}

test('Korean the client writes itself lives only in locale/ko.ts', () => {
  const literal = /'(?:\\.|[^'\\])*[가-힣](?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*[가-힣](?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*[가-힣](?:\\.|[^`\\])*`/g;
  const found = listSources(root).flatMap((file) => {
    const code = fs.readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    return [...code.matchAll(literal)].map((m) => `${path.relative(root, file)}: ${m[0]}`);
  });
  expect(found).toEqual([]);
});
