import type { Hero } from '../types';
import { buildHeroSlot } from '../panel';

const hero = {
  name: '테스터',
  alive: true,
  raceJob: '',
  gender: '',
  level: 1,
  exp: 0,
  expMax: 10,
  canLevelUp: false,
  hp: 10,
  hpMax: 10,
  mp: 4,
  mpMax: 4,
  reviveCoins: 0,
  reviveCoinsMax: 0,
  gold: 0,
  stats: [],
  equipment: {
    weapon: { id: 'sword_01', name: '낡은 검' },
    armor: null,
    accessory: null,
  },
  inventory: [
    { id: 'potion_01', name: '회복 물약', qty: 1, canUse: true, equipSlots: [] },
    { id: 'armor_01', name: '가죽 갑옷', qty: 1, canUse: false, equipSlots: ['armor', 'accessory'] },
  ],
  status: [],
  skills: [],
  companions: [],
} as Hero;

describe('buildHeroSlot', () => {
  test('uses a stable top chip label and keeps item actions out of the top panel', () => {
    const slot = buildHeroSlot(hero);

    expect(slot.chip.short).toBe('주인공');
    expect(slot.chip).not.toHaveProperty('detail');
    expect(slot.panel?.actions).toBeUndefined();
    expect(slot.panel?.meta?.[0]?.text).toBe('Lv 1');
    expect(slot.panel?.sections?.find((section) => section.label === '소지')?.text).toBe('금화(0) · 회복 물약 · 가죽 갑옷');
  });

  test('keeps level-up out of the hero panel title actions', () => {
    const slot = buildHeroSlot({ ...hero, canLevelUp: true });

    expect(slot.chip.dot).toBe(true);
    expect(slot.panel?.titleAction).toBeUndefined();
  });
});
