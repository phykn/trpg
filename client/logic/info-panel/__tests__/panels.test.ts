import { buildPanelSlots } from '../panels';

import type { Hero } from '@/logic/hero';
import type { Quest } from '@/logic/quest';
import type { Subject } from '@/logic/subject';

const hero: Hero = {
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
  equipment: { weapon: null, armor: null, accessory: null },
  inventory: [],
  status: [],
  skills: [],
  companions: [],
};

const subject: Subject = {
  name: '여관 주인',
  alive: true,
  role: '주인',
  raceJob: '인간',
  gender: '남성',
  trust: 4,
  known: ['뒷문을 자주 살핍니다.'],
  level: 1,
  stats: [],
  equipment: { weapon: null, armor: null, accessory: null },
  inventory: [],
  skills: [],
};

const quest: Quest = {
  id: 'quest_01',
  title: '사라진 장부',
  summary: '상인이 숨긴 장부를 확인합니다.',
  giver: '여관 주인',
  difficulty: { label: '보통', tone: 'neutral' },
  goals: ['장부 확인'],
  progressLabel: '진행 중',
  rewards: { gold: 3, exp: 5 },
  status: 'active',
  actions: ['abandon'],
};

describe('buildPanelSlots', () => {
  test('collapses contextual system panels into notes and keeps the hero as sheet', () => {
    const slots = buildPanelSlots(
      { hero, subject, quest, questOffers: [] },
      { questDot: true, subjectDot: true },
    );

    expect(slots.map((slot) => slot.chip.short)).toEqual(['노트', '시트']);
    expect(slots[0].id).toBe('notes');
    expect(slots[0].chip.dot).toBe(true);
    expect(slots[0].panel?.sections?.map((section) => section.label)).toEqual([
      'NPC',
      '목표',
      '요약',
    ]);
    expect(slots[1].id).toBe('hero');
    expect(slots[1].chip.short).toBe('시트');
  });
});
