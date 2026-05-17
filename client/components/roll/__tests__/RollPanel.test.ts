import fs from 'node:fs';
import path from 'node:path';

describe('RollPanel source', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'RollPanel.tsx'), 'utf8');

  test('keeps the roll button disabled instead of showing a rolling indicator', () => {
    expect(source).not.toContain('RollingD20');
    expect(source).not.toContain('rollingLabel');
    expect(source).toContain('disabled={disabled}');
  });

  test('uses a compact header without repeating the pre-roll body text', () => {
    expect(source).not.toContain('{roll.body}');
    expect(source).toContain('items-center justify-between');
    expect(source).toContain('{roll.title}');
    expect(source).toContain('{roll.requiredRoll} {ko.roll.orMore}');
  });
});
