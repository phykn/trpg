import { buildCombatActions } from '../actions';
import type { CombatBadge } from '../types';

describe('buildCombatActions', () => {
  test('builds four combat command actions for the first live enemy', () => {
    const combat: CombatBadge = {
      round: 2,
      turnLabel: '전투 중',
      playerHearts: { current: 3, maximum: 3 },
      enemyHearts: { current: 2, maximum: 3 },
      enemies: [
        { id: 'enemy_01', name: '늑대', alive: true },
      ],
    };

    const actions = buildCombatActions(combat);

    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'combat_command',
        label: '공격',
        combatCommand: { command: 'attack', target_id: 'enemy_01' },
        textFallback: '늑대를 공격합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '기술',
        combatCommand: { command: 'skill', target_id: 'enemy_01' },
        textFallback: '기술을 사용합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '방어',
        combatCommand: { command: 'defend' },
        textFallback: '방어합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '도주',
        combatCommand: { command: 'flee' },
        textFallback: '도망칩니다',
      }),
    ]);
  });
});
