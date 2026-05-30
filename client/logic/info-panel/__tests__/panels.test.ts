import { buildPanelSlots } from '../panels';

import type { Hero } from '@/logic/hero';
import type { Quest } from '@/logic/quest';
import type { Subject } from '@/logic/subject';
import type { Discoveries } from '@/logic/discoveries';

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
  choices: [],
};

const discoveries: Discoveries = {
  clues: [
    {
      id: 'clue_receipt',
      title: '젖은 붉은 영수증',
      summary: '루카라는 이름과 오백이라는 금액이 보입니다.',
      stability: 'scene',
      turnId: 5,
    },
  ],
  memories: [
    {
      id: 'mem_rule',
      title: '혼자 탄 배는 출항할 수 없습니다.',
      summary: '혼자 탄 배는 출항할 수 없습니다.',
      stability: 'campaign',
      turnId: 1,
    },
  ],
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

    expect(slots.map((slot) => slot.chip.short)).toEqual(['테스터', '챕터', '단서']);
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
    expect(slots[1].panel?.sections?.map((section) => section.text)).toEqual([
      '돌아갈 배는 없었다',
      '흰섬의 첫 장입니다.',
    ]);
    expect(slots[1].panel?.actions).toBeUndefined();
    expect(slots[2].id).toBe('discoveries');
    expect(slots[2].panel?.empty).toBe(true);
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

  test('adds discoveries as a top context slot instead of an always-visible panel', () => {
    const slots = buildPanelSlots({
      hero,
      subject,
      chapter: { title: '붉은 종이', summary: '광장에 도착했습니다.' },
      quest,
      questOffers: [],
      discoveries,
      slotDots: { discoveries: true },
    });

    expect(slots.map((slot) => slot.chip.short)).toEqual(['테스터', '챕터', '단서']);
    expect(slots[2].id).toBe('discoveries');
    expect(slots[2].chip.dot).toBe(true);
    expect(slots[2].panel?.title).toBe('');
    expect(slots[2].panel?.sections?.map((section) => [section.label, section.text])).toEqual([
      ['젖은 붉은 영수증', '루카라는 이름과 오백이라는 금액이 보입니다.'],
      ['혼자 탄 배는 출항할 수 없습니다.', '혼자 탄 배는 출항할 수 없습니다.'],
    ]);
  });

  test('deduplicates repeated clue and memory entries in the combined discoveries slot', () => {
    const slots = buildPanelSlots({
      hero,
      subject,
      chapter: { title: '푸른섬', summary: '닫힌 방을 확인합니다.' },
      quest,
      questOffers: [],
      discoveries: {
        clues: [
          {
            id: 'clue_photo',
            title: '탁자 위의 빛바랜 사진들',
            summary: '방 안 탁자 위에는 세워져 있는 몇 장의 빛바랜 사진이 있습니다.',
            stability: 'scene',
            turnId: 8,
          },
        ],
        memories: [
          {
            id: 'mem_photo',
            title: '탁자 위의 빛바랜 사진들',
            summary: '방 안 탁자 위에는 세워져 있는 몇 장의 빛바랜 사진이 있습니다.',
            stability: 'scene',
            turnId: 8,
          },
        ],
      },
    });

    expect(slots[2].panel?.sections?.map((section) => [section.label, section.text])).toEqual([
      ['탁자 위의 빛바랜 사진들', '방 안 탁자 위에는 세워져 있는 몇 장의 빛바랜 사진이 있습니다.'],
    ]);
  });

  test('can mark hero and chapter slots when their contents changed', () => {
    const slots = buildPanelSlots({
      hero,
      subject,
      chapter: { title: '붉은 종이', summary: '광장에 도착했습니다.' },
      quest,
      questOffers: [],
      slotDots: { hero: true, notes: true },
    });

    expect(slots[0].id).toBe('hero');
    expect(slots[0].chip.dot).toBe(true);
    expect(slots[1].id).toBe('notes');
    expect(slots[1].chip.dot).toBe(true);
  });
});
