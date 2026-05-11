import * as fs from 'fs';
import * as path from 'path';

describe('LogItem act entries', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'LogItem.tsx'), 'utf8');

  test('renders act cards without a left accent stripe', () => {
    const start = source.indexOf('function ActDivider');
    const actDivider = start === -1 ? undefined : source.slice(start);

    expect(actDivider).toBeDefined();
    if (!actDivider) {
      throw new Error('ActDivider is missing');
    }
    expect(actDivider).not.toContain('stripeColor');
  });
});
