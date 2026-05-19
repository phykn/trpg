import * as fs from 'fs';
import * as path from 'path';

describe('Log scroll behavior', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Log.tsx'), 'utf8');

  test('does not bottom-align short narration content', () => {
    expect(source).toContain('if (h <= viewportH)');
    expect(source).toContain('scrollToOffset({ offset: 0');
    expect(source).not.toContain('const offset = Math.max(0, h - viewportH);');
  });
});
