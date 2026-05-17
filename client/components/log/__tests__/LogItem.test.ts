import * as fs from 'fs';
import * as path from 'path';

describe('LogItem act entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('renders server act entries as visible status lines', () => {
    expect(source).toContain("case 'act'");
    expect(source).toContain('return <ActMessage text={entry.text} />');
    expect(source).toContain('function ActMessage');
    expect(source).toContain('text-fg-muted');
  });
});

describe('LogItem GM entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('colors GM narration by outcome', () => {
    expect(source).toContain('entry.outcome');
    expect(source).toContain('text-success-fg');
    expect(source).toContain('text-danger-fg');
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
