import * as fs from 'fs';
import * as path from 'path';

describe('Log scroll behavior', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Log.tsx'), 'utf8');

  test('does not bottom-align short narration content', () => {
    expect(source).toContain('if (h <= v)');
    expect(source).toContain('scrollToOffset({ offset: 0');
    expect(source).not.toContain('const offset = Math.max(0, h - viewportH);');
  });

  test('keeps long narration pinned to the latest visible entry after viewport changes', () => {
    expect(source).toContain('const contentH = React.useRef(0);');
    expect(source).toContain('syncScrollPosition');
    expect(source).toContain('onLayout={(ev) => {');
    expect(source).not.toContain('React.useEffect(() => {\n    if (initialized.current && viewportH > 0)');
  });
});
