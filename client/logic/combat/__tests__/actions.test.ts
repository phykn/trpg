import { buildCombatActions } from '../actions';
import type { CombatBadge } from '../types';

function combat(overrides: Partial<CombatBadge> = {}): CombatBadge {
  return {
    round: 2,
    outcome: 'ongoing',
    turnLabel: '전투 중',
    playerHearts: { current: 3, maximum: 3 },
    enemyHearts: { current: 2, maximum: 3 },
    enemies: [
      { id: 'enemy_01', name: '늑대', alive: true },
    ],
    availableSupports: [],
    escapeReady: false,
    enemyPressure: 0,
    ...overrides,
  };
}

describe('buildCombatActions', () => {
  test('builds three combat actions for the first live enemy', () => {
    const actions = buildCombatActions(combat());

    expect(actions).toHaveLength(3);
    expect(actions).toEqual([
      expect.objectContaining({
        kind: 'combat_command',
        label: '공격',
        combatCommand: { command: 'attack', target: 'enemy_01' },
        textFallback: '늑대를 공격합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '방어',
        combatCommand: { command: 'defend' },
        textFallback: '방어합니다',
      }),
      expect.objectContaining({
        kind: 'combat_command',
        label: '도망',
        combatCommand: { command: 'flee' },
        textFallback: '도망칩니다',
      }),
    ]);
  });

  test('uses skill names in attack and defense slots', () => {
    const actions = buildCombatActions(combat({
      availableSupports: [
        {
          id: 'skill_shadow',
          kind: 'skill',
          name: '그림자 찌르기',
          action: 'attack',
          mpCost: 2,
          usable: true,
        },
        {
          id: 'skill_calm_guard',
          kind: 'skill',
          name: '침착한 방어',
          action: 'defend',
          mpCost: 2,
          usable: true,
        },
      ],
    }));

    expect(actions[0]).toMatchObject({
      label: '그림자 찌르기',
      combatCommand: {
        command: 'attack',
        target: 'enemy_01',
        support_id: 'skill_shadow',
        support_kind: 'skill',
      },
    });
    expect(actions[1]).toMatchObject({
      label: '침착한 방어',
      combatCommand: {
        command: 'defend',
        support_id: 'skill_calm_guard',
        support_kind: 'skill',
      },
    });
  });

  test('uses escape label when escape is ready', () => {
    const actions = buildCombatActions(combat({ escapeReady: true }));

    expect(actions).toHaveLength(3);
    expect(actions[2]).toMatchObject({
      label: '도망',
      combatCommand: { command: 'flee' },
    });
  });

  test('uses talk as the situation slot when pressure is present', () => {
    const actions = buildCombatActions(combat({ enemyPressure: 1 }));

    expect(actions).toHaveLength(3);
    expect(actions[2]).toMatchObject({
      label: '대화',
      combatCommand: { command: 'talk', target: 'enemy_01' },
    });
  });
});
