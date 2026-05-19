import {
  buildNeighborhoodGraph,
  buildPlaceMapGraph,
  currentPlaceId,
  mergeStoryGraphs,
  resolvePlaceSelection,
} from '../presenters';
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

  test('drops stale reachable item nodes when they disappear from the next snapshot', () => {
    const merged = mergeStoryGraphs(
      {
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
            id: 'supply_token',
            label: '보급 표식',
            kind: 'item',
            status: 'reachable_item',
            reachable: true,
            description: '바닥에 놓인 표식입니다.',
          },
        ],
        edges: [
          { id: 'item:town:supply_token', source: 'town', target: 'supply_token', label: '줍기', kind: 'item' },
        ],
      },
      {
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
      },
    );

    expect(merged.nodes.some((node) => node.id === 'supply_token')).toBe(false);
    expect(merged.edges.some((edge) => edge.target === 'supply_token')).toBe(false);
  });
});

describe('story graph view presenters', () => {
  test('moves selection to the new current place when the selected node was the previous place', () => {
    const nextNodeIds = new Set(['town', 'archive']);

    expect(resolvePlaceSelection({
      selectedNodeId: 'town',
      previousCurrentPlaceId: 'town',
      nextCurrentPlaceId: 'archive',
      nextNodeIds,
    })).toBe('archive');
  });

  test('keeps an intentional non-current selection across place changes', () => {
    const nextNodeIds = new Set(['town', 'archive', 'gate']);

    expect(resolvePlaceSelection({
      selectedNodeId: 'gate',
      previousCurrentPlaceId: 'town',
      nextCurrentPlaceId: 'archive',
      nextNodeIds,
    })).toBe('gate');
  });

  test('buildPlaceMapGraph keeps only place movement nodes and summarizes reachability', () => {
    const graph = {
      ...baseGraph(),
      edges: [
        { id: 'move:town:gate', source: 'town', target: 'gate', label: '이동', kind: 'move' as const },
        { id: 'move:gate:town', source: 'gate', target: 'town', label: '이동', kind: 'move' as const },
        { id: 'meet:town:guard', source: 'town', target: 'guard', label: '접근', kind: 'meet' as const },
      ],
    };

    const placeMap = buildPlaceMapGraph(graph);

    expect(placeMap.summary).toBe('현재 광장 · 장소 2곳 · 이동 가능 1');
    expect(placeMap.nodes.map((node) => node.id)).toEqual(['town', 'gate']);
    expect(placeMap.edges.map((edge) => edge.id)).toEqual(['move:town:gate']);
    expect(currentPlaceId(placeMap)).toBe('town');
  });

  test('buildNeighborhoodGraph hides unreachable target nodes and dedupes undirected edges', () => {
    const graph: StoryGraphModel = {
      ...baseGraph(),
      nodes: [
        ...baseGraph().nodes,
        {
          id: 'cellar',
          label: '지하실',
          kind: 'location',
          status: 'unreachable_move',
          reachable: false,
          description: '닫혀 있습니다.',
          risk,
          moveDifficulty: null,
        },
        {
          id: 'stranger',
          label: '낯선 사람',
          kind: 'target',
          status: 'unreachable_meet',
          reachable: false,
          level: 1,
          raceJob: '',
          gender: '',
          role: '',
          alive: true,
        },
      ],
      edges: [
        { id: 'move:town:gate', source: 'town', target: 'gate', label: '이동', kind: 'move' },
        { id: 'meet:town:guard', source: 'town', target: 'guard', label: '접근', kind: 'meet' },
        { id: 'meet:guard:town', source: 'guard', target: 'town', label: '접근', kind: 'meet' },
        { id: 'move:town:cellar', source: 'town', target: 'cellar', label: '이동', kind: 'move' },
      ],
    };

    const neighborhood = buildNeighborhoodGraph(graph);

    expect(neighborhood.nodes.map((node) => node.id)).toEqual(['town', 'gate', 'guard']);
    expect(neighborhood.edges.map((edge) => edge.id)).toEqual([
      'move:town:gate',
      'meet:town:guard',
    ]);
  });
});
