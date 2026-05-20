import { buildDecisionState } from '../buildDecisionState';
import type { NarrationCue } from '@/logic/log/types';
import type { Quest } from '@/logic/quest/types';
import type { Place } from '@/logic/story-graph/types';

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

describe('buildDecisionState', () => {
  test('shows compact place and goal without labels', () => {
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
      ['', '버려진 어촌을 거쳐 빈 객석...'],
    ]);
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
