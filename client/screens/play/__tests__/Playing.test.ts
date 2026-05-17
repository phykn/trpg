import * as fs from 'fs';
import * as path from 'path';

describe('Playing overlay layering', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '..', 'Playing.tsx'), 'utf8');

  test('keeps the bottom composer above panel dismissal overlays', () => {
    expect(source).toContain('activeId !== null || nearbyOpen ? 10 : 0');
  });

  test('uses shared panel slot builder so active quests and offers stay separate', () => {
    expect(source).toContain('buildPanelSlots');
    expect(source).not.toContain('quest ?? questOffers[0] ?? null');
  });

  test('keeps free text composer available during combat', () => {
    expect(source).toContain('combat ? (');
    expect(source).toContain('<CombatStrip');
    expect(source).toContain('locked={pendingConfirmation !== null}');
  });
});
