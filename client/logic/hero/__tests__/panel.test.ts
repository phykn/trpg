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
  test('builds graph actions for usable inventory and equipped items', () => {
    const slot = buildHeroSlot(hero);

    const actions = slot.panel?.actions?.flatMap((group) => group.items) ?? [];

    expect(actions).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'graph_action',
        label: '회복 물약 사용',
        graphAction: { verb: 'use', what: 'potion_01' },
      }),
      expect.objectContaining({
        kind: 'graph_action',
        label: '가죽 갑옷 장비',
        graphAction: { verb: 'transfer', what: 'armor_01', how: 'equip', to: 'armor' },
      }),
      expect.objectContaining({
        kind: 'graph_action',
        label: '낡은 검 해제',
        graphAction: { verb: 'transfer', what: 'sword_01', how: 'unequip' },
      }),
    ]));
  });
});
