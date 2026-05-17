import fs from 'node:fs';
import path from 'node:path';

describe('CombatStrip source', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'CombatStrip.tsx'), 'utf8');

  test('does not render a rolling indicator while combat narration is streaming', () => {
    expect(source).not.toContain('RollingD20');
    expect(source).not.toContain('ko.roll.rolling');
    expect(source).not.toContain('combat.lastRoll');
    expect(source).not.toContain('combat.lastDc');
    expect(source).toContain('disabled={actionDisabled}');
  });
});
