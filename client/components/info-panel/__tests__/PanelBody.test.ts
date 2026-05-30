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

  test('does not reserve large empty space for short non-empty panels', () => {
    expect(source).not.toContain('style={{ minHeight: 160 }}');
    expect(source).toContain('className="px-4 py-3 gap-2.5"');
  });

  test('does not use repeated row labels as React keys', () => {
    expect(source).toContain('function sectionRenderKey');
    expect(source).toContain('const rowKey = sectionRenderKey(section, index);');
    expect(source).toContain('key={rowKey}');
    expect(source).toContain('id={rowKey}');
    expect(source).not.toContain('key={section.label}');
  });
});
