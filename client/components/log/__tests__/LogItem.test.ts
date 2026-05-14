import * as fs from 'fs';
import * as path from 'path';

describe('LogItem act entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('does not render server act entries as visible system cards', () => {
    expect(source).toContain("case 'act'");
    expect(source).toContain('return null');
    expect(source).not.toContain('ActDivider');
  });
});

describe('RollResult entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'RollResult.tsx'), 'utf8');

  test('renders roll outcomes as inline result lines, not system cards', () => {
    expect(source).not.toContain('Surface');
    expect(source).toContain('borderLeftWidth');
    expect(source).toContain('tone.label');
  });

  test('does not include partial roll outcome handling', () => {
    expect(source).not.toContain('partial');
  });
});
