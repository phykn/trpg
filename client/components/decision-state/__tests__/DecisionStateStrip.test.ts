import * as fs from 'fs';
import * as path from 'path';

describe('DecisionStateStrip layout', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'DecisionStateStrip.tsx'), 'utf8');

  test('keeps horizontal strip items at content height', () => {
    expect(source).toContain("alignItems: 'flex-start'");
  });
});
