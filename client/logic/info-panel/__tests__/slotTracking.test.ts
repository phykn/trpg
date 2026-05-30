import { buildPanelSlotContentKeys, buildPanelSlotDots, isTopPanelSlotId } from '../slotTracking';

describe('panel slot tracking', () => {
  test('builds stable content keys for top context slots', () => {
    const keys = buildPanelSlotContentKeys({
      gameId: 'game_01',
      hero: null,
      chapter: { title: '붉은 종이', summary: '광장에 도착했습니다.' },
      quest: null,
      questOffers: [],
      discoveries: { clues: [], memories: [] },
      scenarioCompleted: false,
    });

    expect(Object.keys(keys)).toEqual(['hero', 'notes', 'discoveries']);
    expect(keys.hero).toBe('null');
    expect(keys.notes).toContain('붉은 종이');
    expect(keys.discoveries).toContain('"clues":[]');
  });

  test('marks changed slots unless the slot is active', () => {
    const current = {
      hero: 'hero:2',
      notes: 'notes:2',
      discoveries: 'discoveries:2',
    };
    const seen = {
      hero: 'hero:1',
      notes: 'notes:1',
      discoveries: 'discoveries:1',
    };

    expect(buildPanelSlotDots('notes', seen, current)).toEqual({
      hero: true,
      notes: false,
      discoveries: true,
    });
  });

  test('recognizes only top context panel ids', () => {
    expect(isTopPanelSlotId('hero')).toBe(true);
    expect(isTopPanelSlotId('notes')).toBe(true);
    expect(isTopPanelSlotId('discoveries')).toBe(true);
    expect(isTopPanelSlotId('nearby')).toBe(false);
    expect(isTopPanelSlotId(null)).toBe(false);
  });
});
