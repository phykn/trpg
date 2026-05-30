import * as fs from 'fs';
import * as path from 'path';

describe('IconButton labeled mode', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'IconButton.tsx'), 'utf8');

  test('can render a short visible text label next to the icon', () => {
    expect(source).toContain('text?: string');
    expect(source).toContain('{text ? (');
    expect(source).toContain('{text}');
    expect(source).toContain('w-8 h-8');
  });
});
