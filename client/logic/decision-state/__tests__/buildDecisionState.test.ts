import { buildDecisionState } from '../buildDecisionState';
import type { NarrationCue } from '@/logic/log/types';
import type { Quest } from '@/logic/quest/types';
import type { Place } from '@/logic/story-graph/types';
import type { CombatBadge } from '@/logic/combat/types';
import type { Subject } from '@/logic/subject/types';

const place: Place = {
  name: '마을',
  description: '작은 마을입니다.',
  dayPhase: '낮',
  weather: ['맑음'],
  surroundings: [],
  targets: [],
  risk: { label: '안전', tone: 'neutral' },
};

const quest: Quest = {
  id: 'quest-1',
  title: '북문 조사',
  summary: '북문에서 이상한 흔적이 발견되었습니다.',
  giver: '경비대장',
  difficulty: { label: '보통', tone: 'neutral' },
  goals: ['북문 흔적 확인', '경비대장에게 보고'],
  progressLabel: '진행 중',
  rewards: { gold: 10, exp: 5 },
  status: 'active',
  actions: ['abandon'],
};

const subject: Subject = {
  name: '말없는 선장',
  alive: true,
  role: '선장',
  raceJob: '인간',
  gender: '남성',
  level: 1,
};

const combat: CombatBadge = {
  round: 1,
  outcome: 'ongoing',
  turnLabel: '전투',
  playerHearts: { current: 3, maximum: 3 },
  enemyHearts: { current: 2, maximum: 2 },
  enemies: [{ id: 'wolf', name: '안개 늑대', alive: true }],
  availableSupports: [],
  escapeReady: false,
  enemyPressure: 0,
};

describe('buildDecisionState', () => {
  test('shows compact place without duplicating quest goals', () => {
    const items = buildDecisionState({
      place: { ...place, name: '칭호의 안개 숲' },
      quest: {
        ...quest,
        goals: ['버려진 어촌을 거쳐 빈 객석의 극장으로 향합니다'],
      },
      combat: null,
      heroStatus: [],
      latestCues: [],
    });

    expect(items.map((item) => [item.label, item.text])).toEqual([
      ['', '칭호의 안개 숲'],
    ]);
  });

  test('adds compact hero level, HP, and MP when vitals are available', () => {
    const items = buildDecisionState({
      place,
      quest: null,
      combat: null,
      heroVitals: { level: 4, exp: 6, expMax: 10, hp: 8, hpMax: 12, mp: 3, mpMax: 5 },
      heroStatus: [],
      latestCues: [],
    });

    expect(items.map((item) => [item.id, item.label, item.text, item.tone, item.progress])).toEqual([
      ['hero:level', 'LV', '4', 'level', 0.6],
      ['hero:hp', 'HP', '8/12', 'hp', undefined],
      ['hero:mp', 'MP', '3/5', 'mp', undefined],
      ['place', '', '마을', 'neutral', undefined],
    ]);
  });

  test('shows the faced subject after place', () => {
    const items = buildDecisionState({
      place,
      quest: null,
      combat: null,
      subject,
      heroVitals: { level: 4, exp: 6, expMax: 10, hp: 8, hpMax: 12, mp: 3, mpMax: 5 },
      heroStatus: [],
      latestCues: [],
    });

    expect(items.map((item) => [item.id, item.label, item.text, item.tone])).toEqual([
      ['hero:level', 'LV', '4', 'level'],
      ['hero:hp', 'HP', '8/12', 'hp'],
      ['hero:mp', 'MP', '3/5', 'mp'],
      ['place', '', '마을', 'neutral'],
      ['subject:faced', '', '말없는 선장', 'accent'],
    ]);
  });

  test('prefers the active combat enemy over the faced subject', () => {
    const items = buildDecisionState({
      place,
      quest: null,
      combat,
      subject,
      heroVitals: { level: 4, exp: 6, expMax: 10, hp: 8, hpMax: 12, mp: 3, mpMax: 5 },
      heroStatus: [],
      latestCues: [],
    });

    expect(items.find((item) => item.id === 'subject:faced')?.text).toBe('안개 늑대');
  });

  test('shows place when no active goal is available', () => {
    const items = buildDecisionState({
      place,
      quest: null,
      combat: null,
      heroStatus: [],
      latestCues: [],
    });

    expect(items.map((item) => item.text)).toEqual(['마을']);
  });

  test('shows scenario completion when no active quest remains', () => {
    const items = buildDecisionState({
      place: null,
      quest: null,
      combat: null,
      heroStatus: [],
      latestCues: [],
      scenarioCompleted: true,
    });

    expect(items).toEqual([
      {
        id: 'scenario:completed',
        label: '',
        text: '이야기 완료',
        tone: 'accent',
      },
    ]);
  });

  test('promotes a temporary opportunity cue', () => {
    const cue: NarrationCue = {
      kind: 'opportunity',
      label: '기회',
      text: '문틈을 살필 수 있음',
      scope: 'temporary',
    };

    const items = buildDecisionState({
      place: null,
      quest: null,
      combat: null,
      heroStatus: [],
      latestCues: [cue],
    });

    expect(items).toEqual([
      {
        id: 'cue:0',
        label: '이번 선택',
        text: '문틈을 살필 수 있음',
        tone: 'accent',
        temporary: true,
      },
    ]);
  });

  test('does not promote delta cues into the temporary decision strip', () => {
    const cue: NarrationCue = {
      kind: 'change',
      label: '변화',
      text: '평판이 흔들립니다',
      scope: 'delta',
    };

    const items = buildDecisionState({
      place: null,
      quest: null,
      combat: null,
      heroStatus: [],
      latestCues: [cue],
    });

    expect(items).toEqual([]);
  });
});
