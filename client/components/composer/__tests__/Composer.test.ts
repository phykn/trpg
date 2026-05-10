import * as fs from 'fs';
import * as path from 'path';

describe('Composer quick actions', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Composer.tsx'), 'utf8');

  test('renders command actions in the bottom composer before text suggestions', () => {
    const quickActionsIndex = source.indexOf('quickActions');
    const suggestionsIndex = source.indexOf('suggestions.map');

    expect(quickActionsIndex).toBeGreaterThan(-1);
    expect(suggestionsIndex).toBeGreaterThan(-1);
    expect(quickActionsIndex).toBeLessThan(suggestionsIndex);
  });
});
