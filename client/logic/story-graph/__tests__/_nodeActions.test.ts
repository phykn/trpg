import { actionForNode } from '../_nodeActions';
import type { LocationNode, TargetNode } from '../types';

describe('actionForNode', () => {
  test('uses an explicit graph move action for reachable locations', () => {
    const action = actionForNode({
      id: 'forest',
      label: '숲길',
      kind: 'location',
      status: 'reachable_move',
      reachable: true,
      description: '나무가 빽빽합니다.',
      risk: { label: '보통', tone: 'neutral' },
      moveDifficulty: null,
    } satisfies LocationNode);

    expect(action).toMatchObject({
      kind: 'graph_action',
      graphAction: { verb: 'move', to: 'forest' },
      textFallback: '숲길로 이동합니다',
    });
  });

  test('keeps reachable targets as text because approach is narrative input', () => {
    const action = actionForNode({
      id: 'wolf_01',
      label: '늑대',
      kind: 'target',
      status: 'reachable_meet',
      reachable: true,
      level: 1,
      raceJob: '',
      gender: '',
      role: '',
      alive: true,
      trust: 0,
    } satisfies TargetNode);

    expect(action).toMatchObject({
      kind: 'text',
      text: '늑대에게 접근합니다',
    });
  });
});
