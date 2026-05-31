import * as fs from 'fs';
import * as path from 'path';

describe('LabeledRow expand and measurement behavior', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LabeledRow.tsx'), 'utf8');

  test('can separate repeated labels by a stable id', () => {
    expect(source).toContain('id?: string;');
    expect(source).toContain('useExpandGroup(id ?? label)');
  });

  test('does not duplicate text in a hidden measurement node', () => {
    expect(source).toContain('function canExpandText');
    expect(source).not.toContain('opacity-0');
    expect(source).not.toContain('onLayout={(e)');
  });

  test('renders multiline text with a separate title and expandable affordance', () => {
    expect(source).toContain('const lines = text.split');
    expect(source).toContain('const titleLine = canUseTitleBodyLayout ? lines[0] : null;');
    expect(source).toContain('text-fg-muted');
    expect(source).toContain('accessibilityLabel={expanded ? ko.panel.collapse : ko.panel.expand}');
  });
});
