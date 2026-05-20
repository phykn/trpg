import * as fs from 'fs';
import * as path from 'path';

describe('DecisionStateStrip layout', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'DecisionStateStrip.tsx'), 'utf8');

  test('keeps horizontal strip items at content height', () => {
    expect(source).toContain("alignItems: 'flex-start'");
    expect(source).toContain('style={{ flexGrow: 0, flexShrink: 0 }}');
  });

  test('renders labels only when present and keeps chips compact', () => {
    expect(source).not.toContain('numberOfLines={2}');
    expect(source).toContain('{item.label ? (');
    expect(source).toContain('style={{ maxWidth: 180, flexShrink: 0 }}');
    expect(source).toContain('numberOfLines={1}');
  });
});
