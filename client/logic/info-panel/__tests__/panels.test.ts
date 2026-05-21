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
  level: 1,
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
  test('keeps info and adds a hero-named top button with hero sheet details', () => {
    const slots = buildPanelSlots({
      hero,
      subject,
      chapter: { title: '돌아갈 배는 없었다', summary: '흰섬의 첫 장입니다.' },
      quest,
      questOffers: [],
    });

    expect(slots.map((slot) => slot.chip.short)).toEqual(['테스터', '챕터']);
    expect(slots[0].id).toBe('hero');
    expect(slots[0].panel?.title).toBe('');
    expect(slots[0].panel?.meta).toBeUndefined();
    expect(slots[0].panel?.sections?.map((section) => section.label)).toEqual([
      '능력',
      '장비',
      '소지',
      '기술',
      '동료',
      '특징',
    ]);
    expect(slots[0].panel?.actions).toBeUndefined();
    expect(slots[0].panel?.barSplit).toBeUndefined();
    expect(slots[1].id).toBe('notes');
    expect(slots[1].panel?.title).toBe('');
    expect(slots[1].panel?.meta).toBeUndefined();
    expect(slots[1].panel?.sections?.map((section) => section.label)).toEqual([
      '챕터',
      '요약',
    ]);
    expect(slots[1].panel?.actions).toBeUndefined();
  });

  test('shows scenario completion when no active quest remains', () => {
    const slots = buildPanelSlots({
      hero,
      subject: null,
      chapter: { title: '끝나지 않았다는 불', summary: '' },
      scenarioCompleted: true,
      quest: null,
      questOffers: [],
    });

    expect(slots[0].panel?.sections?.slice(0, 2).map((section) => [section.label, section.text])).toEqual([
      ['능력', undefined],
      ['장비', '—'],
    ]);
  });
});
