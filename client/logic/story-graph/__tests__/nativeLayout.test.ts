import { layoutNativeStoryGraph } from '../nativeLayout';
import type { StoryGraphModel } from '../types';

const graph: StoryGraphModel = {
  summary: '테스트 허브',
  nodes: [
    {
      id: 'hub',
      label: '테스트 허브',
      kind: 'place',
      status: 'current',
      reachable: true,
      description: '현재 위치입니다.',
      risk: { label: '보통', tone: 'neutral' },
      dayPhase: '',
      weather: [],
    },
    {
      id: 'ready_room',
      label: '준비실',
      kind: 'location',
      status: 'reachable_move',
      reachable: true,
      description: '이동 가능한 방입니다.',
      risk: { label: '보통', tone: 'neutral' },
      moveDifficulty: null,
    },
    {
      id: 'locked_room',
      label: '잠긴 방',
      kind: 'location',
      status: 'unreachable_move',
      reachable: false,
      description: '아직 이동할 수 없습니다.',
      risk: { label: '위험', tone: 'bad' },
      moveDifficulty: '13 이상',
    },
  ],
  edges: [
    { id: 'hub-ready', source: 'hub', target: 'ready_room', label: '이동', kind: 'move' },
    { id: 'hub-locked', source: 'hub', target: 'locked_room', label: '이동', kind: 'move' },
    { id: 'missing', source: 'hub', target: 'missing_room', label: '이동', kind: 'move' },
  ],
};

describe('layoutNativeStoryGraph', () => {
  test('places the current map node at the visual center and spreads locations around it', () => {
    const layout = layoutNativeStoryGraph(graph, {
      width: 320,
      height: 200,
      centerNodeId: 'hub',
      selectedNodeId: 'ready_room',
    });

    expect(layout.nodes.find((node) => node.id === 'hub')).toMatchObject({
      id: 'hub',
      x: 160,
      y: 92,
      current: true,
      selected: false,
    });
    expect(layout.nodes.find((node) => node.id === 'ready_room')).toMatchObject({
      reachable: true,
      selected: true,
    });
    expect(layout.nodes.find((node) => node.id === 'locked_room')).toMatchObject({
      reachable: false,
    });
    expect(new Set(layout.nodes.map((node) => `${node.x},${node.y}`)).size).toBe(3);
  });

  test('keeps only edges whose endpoints are visible', () => {
    const layout = layoutNativeStoryGraph(graph, {
      width: 320,
      height: 200,
      centerNodeId: 'hub',
      selectedNodeId: null,
    });

    expect(layout.edges.map((edge) => edge.id)).toEqual(['hub-ready', 'hub-locked']);
  });
});
