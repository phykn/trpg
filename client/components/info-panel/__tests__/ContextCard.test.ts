import * as fs from 'fs';
import * as path from 'path';

describe('ContextCard panel layout', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'ContextCard.tsx'), 'utf8');

  test('renders open panels in normal layout instead of overlaying the narration log', () => {
    expect(source).toContain('CONTEXT_PANEL_MAX_HEIGHT');
    expect(source).toContain('ScrollView');
    expect(source).toContain('showsVerticalScrollIndicator={false}');
    expect(source).not.toContain('marginBottom: -FLOAT_BUFFER');
    expect(source).not.toContain("position: 'absolute'");
  });

  test('ties tab selected state directly to the active panel id', () => {
    expect(source).toContain('active={s.id === activeId}');
  });
});
