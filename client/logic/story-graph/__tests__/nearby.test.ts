import { buildNearbyPanel } from '../nearby';
import type { StoryGraphModel } from '../types';

const graph: StoryGraphModel = {
  summary: '비 내리는 여관',
  nodes: [
    {
      id: 'hero',
      label: '아린',
      kind: 'hero',
      status: null,
      reachable: true,
      level: 1,
      raceJob: '',
      gender: '',
      role: '',
      alive: true,
      known: [],
    },
    {
      id: 'hall',
      label: '홀',
      kind: 'place',
      status: 'current',
      reachable: true,
      description: '비 내리는 여관의 홀입니다.',
      risk: { label: '보통', tone: 'neutral' },
      dayPhase: '',
      weather: [],
    },
    {
      id: 'owner',
      label: '여관 주인',
      kind: 'subject',
      status: 'engaged',
      reachable: true,
      level: 1,
      raceJob: '',
      gender: '',
      role: '주인',
      alive: true,
      trust: 0,
      known: ['불안한 표정으로 뒷문을 살핍니다.'],
    },
    {
      id: 'guest',
      label: '구석의 손님',
      kind: 'target',
      status: 'reachable_meet',
      reachable: true,
      level: 1,
      raceJob: '',
      gender: '',
      role: '수상한 손님',
      alive: true,
      trust: -12,
    },
    {
      id: 'backdoor',
      label: '뒷문',
      kind: 'location',
      status: 'reachable_move',
      reachable: true,
      description: '잠겨 있고, 아래로 빗물이 스며듭니다.',
      risk: { label: '보통', tone: 'neutral' },
      moveDifficulty: null,
    },
    {
      id: 'notice',
      label: '낡은 게시판을 살펴본다',
      kind: 'quest',
      status: null,
      reachable: true,
      questDifficulty: '보통',
      rewards: { gold: 0, exp: 0 },
      giver: '',
      goals: ['젖은 의뢰서가 한 장 남아 있습니다.'],
      summary: '젖은 의뢰서가 한 장 남아 있습니다.',
    },
  ],
  edges: [],
};

describe('buildNearbyPanel', () => {
  test('summarizes one-hop people, places, and tasks with actionable rows', () => {
    const panel = buildNearbyPanel(graph);

    expect(panel.summary).toBe('인물 2 · 장소 1 · 할 일 1');
    expect(panel.items.map((item) => [item.title, item.action?.label])).toEqual([
      ['여관 주인', '대화'],
      ['구석의 손님', '접근'],
      ['뒷문', '이동'],
      ['낡은 게시판을 살펴본다', '살펴보기'],
    ]);
  });
});
