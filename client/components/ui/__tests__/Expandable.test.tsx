import * as fs from 'fs';
import * as path from 'path';

describe('Expandable hidden measurement text', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Expandable.tsx'), 'utf8');

  test('keeps measurement-only text out of the accessibility tree', () => {
    expect(source).toContain('accessibilityElementsHidden');
    expect(source).toContain('importantForAccessibility="no-hide-descendants"');
  });
});
