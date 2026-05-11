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
});
