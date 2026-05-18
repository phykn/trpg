import { buildDecisionState } from '../buildDecisionState';
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
  test('includes place and first active quest goal', () => {
    const items = buildDecisionState({
      place,
      quest,
      combat: null,
      heroStatus: [],
      latestCues: [],
    });

    expect(items.map((item) => item.text)).toEqual(['마을', '북문 흔적 확인']);
  });

  test('promotes a temporary opportunity cue', () => {
    const items = buildDecisionState({
      place: null,
      quest: null,
      combat: null,
      heroStatus: [],
      latestCues: [{ text: '문틈을 살필 수 있음', tone: 'opportunity' }],
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
});
