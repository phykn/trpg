const fs = require('fs');
const path = require('path');

const CLIENT_ROOT = path.resolve(__dirname, '..', '..');

function sourceFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry: { name: string; isDirectory: () => boolean }) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (['__tests__', 'node_modules', '.expo', 'dist'].includes(entry.name)) return [];
      return sourceFiles(full);
    }
    if (!/\.(ts|tsx)$/.test(entry.name)) return [];
    if (full.endsWith(path.join('locale', 'ko.ts'))) return [];
    return [full];
  });
}

function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/.*$/gm, '');
}

function koreanStringLiterals(source: string): string[] {
  const stripped = stripComments(source);
  const stringLiteral = /'(?:\\.|[^'\\])*[가-힣](?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*[가-힣](?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*[가-힣](?:\\.|[^`\\])*`/g;
  return Array.from(stripped.matchAll(stringLiteral))
    .map((match) => match[0]);
}

describe('client locale boundary', () => {
  test('keeps Korean client-owned strings in locale/ko.ts', () => {
    const offenders = sourceFiles(CLIENT_ROOT)
      .map((file) => ({
        file: path.relative(CLIENT_ROOT, file),
        literals: koreanStringLiterals(fs.readFileSync(file, 'utf8')),
      }))
      .filter((entry) => entry.literals.length > 0);

    expect(offenders).toEqual([]);
  });
});
