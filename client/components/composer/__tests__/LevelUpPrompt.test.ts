import * as fs from 'fs';
import * as path from 'path';

describe('LevelUpPrompt mobile selectors', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LevelUpPrompt.tsx'), 'utf8');

  test('exposes stable test ids for growth choices and footer actions', () => {
    expect(source).toContain('testID={`level-growth-${choice.id}`}');
    expect(source).toContain("id: 'max_hp'");
    expect(source).toContain("id: 'max_mp'");
    expect(source).toContain('testID="level-cancel"');
    expect(source).toContain('testID="level-confirm"');
  });

  test('does not flash fallback choices while server choices are loading', () => {
    expect(source).toContain('choices.length > 0 ? choices : loading ? [] : CHOICES');
    expect(source).toContain('disabled={!selected || loading}');
  });

  test('keeps many growth choices readable on mobile', () => {
    expect(source).toContain('minWidth: 96');
    expect(source).toContain('flexGrow: 1');
    expect(source).toContain('numberOfLines={2}');
    expect(source).not.toContain('flex: 1,\n            height: 34');
  });
});
