import { mergeStoryGraphs } from '../presenters';
import type { StoryGraphModel } from '../types';

const risk = { label: '보통', tone: 'neutral' as const };

function baseGraph(): StoryGraphModel {
  return {
    summary: '광장',
    nodes: [
      {
        id: 'town',
        label: '광장',
        kind: 'place',
        status: 'current',
        reachable: true,
        description: '사람들이 모여 있습니다.',
        risk,
        dayPhase: '',
        weather: [],
      },
      {
        id: 'gate',
        label: '성문',
        kind: 'location',
        status: 'reachable_move',
        reachable: true,
        description: '성 밖으로 이어집니다.',
        risk,
        moveDifficulty: null,
      },
      {
        id: 'guard',
        label: '경비병',
        kind: 'target',
        status: 'reachable_meet',
        reachable: true,
        level: 1,
        raceJob: '',
        gender: '',
        role: '문지기',
        alive: true,
      },
    ],
    edges: [
      { id: 'move:town:gate', source: 'town', target: 'gate', label: '이동', kind: 'move' },
      { id: 'meet:town:guard', source: 'town', target: 'guard', label: '접근', kind: 'meet' },
    ],
  };
}

describe('mergeStoryGraphs', () => {
  test('demotes previously reachable locations and targets when they disappear from the next snapshot', () => {
    const merged = mergeStoryGraphs(baseGraph(), {
      summary: '광장',
      nodes: [
        {
          id: 'town',
          label: '광장',
          kind: 'place',
          status: 'current',
          reachable: true,
          description: '사람들이 모여 있습니다.',
          risk,
          dayPhase: '',
          weather: [],
        },
      ],
      edges: [],
    });

    expect(merged.nodes.find((node) => node.id === 'gate')).toMatchObject({
      kind: 'location',
      status: 'unreachable_move',
      reachable: false,
    });
    expect(merged.nodes.find((node) => node.id === 'guard')).toMatchObject({
      kind: 'target',
      status: 'unreachable_meet',
      reachable: false,
    });
  });
});
