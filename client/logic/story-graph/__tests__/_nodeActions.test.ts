import { actionsForNode } from '../_nodeActions';
import type { LocationNode, TargetNode } from '../types';

describe('actionsForNode', () => {
  test('uses an explicit graph move action for reachable locations', () => {
    const actions = actionsForNode({
      id: 'forest',
      label: '숲길',
      kind: 'location',
      status: 'reachable_move',
      reachable: true,
      description: '나무가 빽빽합니다.',
      risk: { label: '보통', tone: 'neutral' },
      moveDifficulty: null,
    } satisfies LocationNode);

    expect(actions).toHaveLength(1);
    expect(actions[0]).toMatchObject({
      kind: 'graph_action',
      graphAction: { verb: 'move', to: 'forest' },
      textFallback: '숲길로 이동합니다',
    });
  });

  test('offers both attack and approach for reachable targets', () => {
    const actions = actionsForNode({
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
    } satisfies TargetNode);

    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'graph_action',
        label: '공격',
        graphAction: { verb: 'attack', what: 'wolf_01' },
        textFallback: '늑대를 공격합니다',
      }),
      expect.objectContaining({
        kind: 'text',
        label: '접근',
        text: '늑대에게 접근합니다',
      }),
    ]);
  });

  test('does not offer attack for a non-attackable reachable target', () => {
    const actions = actionsForNode({
      id: 'child_01',
      label: '아이',
      kind: 'target',
      status: 'reachable_meet',
      reachable: true,
      level: 1,
      raceJob: '',
      gender: '',
      role: '',
      alive: true,
      canAttack: false,
    } as TargetNode & { canAttack: false });

    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'text',
        label: '접근',
        text: '아이에게 접근합니다',
      }),
    ]);
  });

  test('offers a pickup graph action for reachable items', () => {
    const actions = actionsForNode({
      id: 'supply_token',
      label: '보급 표식',
      kind: 'item',
      status: 'reachable_item',
      reachable: true,
      description: '바닥에 놓인 작은 표식입니다.',
    } as any);

    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'graph_action',
        label: '줍기',
        graphAction: { verb: 'transfer', what: 'supply_token' },
        textFallback: '보급 표식을 줍습니다',
      }),
    ]);
  });
});
