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

  test('closes the nearby panel when free text or a suggestion is sent', () => {
    expect(source).toContain('setNearbyOpen(false);');
    expect(source).toContain('setExpandedNearbyId(null);');
    expect(source.indexOf('const sendText = (raw: string) => {')).toBeLessThan(
      source.indexOf('Keyboard.dismiss();'),
    );
  });

  test('keeps the nearby panel scrollable when many items are listed', () => {
    expect(source).toContain('ScrollView');
    expect(source).toContain('NEARBY_PANEL_MAX_HEIGHT');
    expect(source).toContain('keyboardShouldPersistTaps="handled"');
    expect(source).toContain('showsVerticalScrollIndicator={false}');
  });

  test('keeps nearby row expansion separate from nested action buttons', () => {
    expect(source).toContain('className="flex-row items-center gap-2 rounded-sm bg-canvas-inset px-2 py-2"');
    expect(source).toContain('accessibilityLabel={`${item.title} ${item.action.label}`}');
  });
});
