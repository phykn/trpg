import * as fs from 'fs';
import * as path from 'path';

describe('RootLayout mobile web keyboard behavior', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', '_layout.tsx'), 'utf8');

  test('opts Android Chrome web into virtual keyboard overlay mode', () => {
    expect(source).toContain("virtualKeyboard' in navigator");
    expect(source).toContain('webNavigator.virtualKeyboard.overlaysContent = true');
    expect(source).toContain('interactive-widget=overlays-content');
  });
});
