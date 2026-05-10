import { buildCombatActions } from '../actions';
import type { CombatBadge } from '../types';

describe('buildCombatActions', () => {
  test('builds simple graph actions for the first live enemy', () => {
    const combat: CombatBadge = {
      round: 2,
      turnLabel: '전투 중',
      enemies: [
        { id: 'enemy_01', name: '늑대', hp: 9, hpMax: 28, alive: true },
      ],
    };

    const actions = buildCombatActions(combat);

    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'graph_action',
        label: '공격',
        graphAction: { verb: 'attack', what: 'enemy_01' },
        textFallback: '늑대를 공격합니다',
      }),
      expect.objectContaining({
        kind: 'graph_action',
        label: '방어',
        graphAction: { verb: 'pass' },
        textFallback: '방어합니다',
      }),
      expect.objectContaining({
        kind: 'graph_action',
        label: '도망',
        graphAction: { verb: 'move', how: 'flee' },
        textFallback: '도망칩니다',
      }),
    ]);
  });
});
