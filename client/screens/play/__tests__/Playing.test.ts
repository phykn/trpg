import * as fs from 'fs';
import * as path from 'path';

describe('Playing overlay layering', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Playing.tsx'), 'utf8');

  test('keeps the bottom composer above panel dismissal overlays', () => {
    expect(source).toContain('activeId !== null || nearbyOpen ? 10 : 0');
  });
});
