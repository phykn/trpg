import * as fs from 'fs';
import * as path from 'path';

describe('StoryGraphCanvas web lifecycle', () => {
  test('does not rebuild Cytoscape when only the node selection handler changes', () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, '..', 'StoryGraphCanvas.web.tsx'),
      'utf8',
    );
    const lifecycleDeps = source.match(/\}, \[graphIdentityKey[^\]]+\]\);/);

    expect(lifecycleDeps?.[0]).toBeDefined();
    expect(lifecycleDeps?.[0]).not.toContain('onNodeSelect');
  });
});
