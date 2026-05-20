import * as fs from 'fs';
import * as path from 'path';

describe('PanelBody header layout', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'PanelBody.tsx'), 'utf8');

  test('keeps title actions in the same left cluster as the title', () => {
    const titleGroup = source.match(/function HeaderTitleGroup[\s\S]*?\n}\n\nexport function PanelBody/)?.[0];

    expect(titleGroup).toBeDefined();
    if (!titleGroup) {
      throw new Error('HeaderTitleGroup is missing');
    }
    expect(titleGroup.indexOf('<ExpandableTitle')).toBeLessThan(
      titleGroup.indexOf('panel.titleAction'),
    );

    expect(source).toContain('{showHeader && (');
    expect(source).toContain('<View className="flex-row items-center gap-2" style={{ minHeight: 22 }}>');
    expect(source.indexOf('<HeaderTitleGroup panel={panel} />')).toBeLessThan(
      source.indexOf('<ExpandableMeta segments={panel.meta} />'),
    );
  });
});
