import * as fs from 'fs';
import * as path from 'path';

describe('LogItem act entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('renders non-combat server act entries as visible status lines', () => {
    expect(source).toContain("case 'act'");
    expect(source).toContain('isCombatActSummary(entry.text) ? null : <ActMessage text={entry.text} />');
    expect(source).toContain('function ActMessage');
    expect(source).toContain('text-fg-muted');
  });

  test('hides combat act summaries already narrated by the combat panel and GM text', () => {
    expect(source).toContain('function isCombatActSummary');
    expect(source).toContain('ko.log.combatActSummaries');
  });
});

describe('LogItem GM entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('colors GM narration by outcome', () => {
    expect(source).toContain('entry.outcome');
    expect(source).toContain('text-success-fg');
    expect(source).toContain('text-danger-fg');
  });

  test('renders narration cues from server-composed GM entries', () => {
    expect(source).toContain('function NarrationCues');
    expect(source).toContain('entry.cues');
    expect(source).toContain('ko.cue.groupLabel');
    expect(source).toContain('cue.label');
    expect(source).toContain('cue.text');
  });
});

describe('RollResult entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'RollResult.tsx'), 'utf8');

  test('renders roll outcomes as inline result lines, not system cards', () => {
    expect(source).not.toContain('Surface');
    expect(source).not.toContain('borderLeftWidth');
    expect(source).toContain('tone.label');
  });

  test('does not include partial roll outcome handling', () => {
    expect(source).not.toContain('partial');
  });
});
