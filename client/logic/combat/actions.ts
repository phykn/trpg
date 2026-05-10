import { compose, ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import type { CombatBadge } from './types';

export function buildCombatActions(combat: CombatBadge): PanelAction[] {
  const target = combat.enemies.find((enemy) => enemy.alive);
  if (!target) return [];
  const targetId = typeof target.id === 'string' && target.id ? target.id : target.name;
  return [
    {
      kind: 'graph_action',
      label: ko.combat.attack,
      graphAction: { verb: 'attack', what: targetId },
      textFallback: compose.attack(target.name),
    },
    {
      kind: 'graph_action',
      label: ko.combat.defend,
      graphAction: { verb: 'pass' },
      textFallback: compose.defend(),
    },
    {
      kind: 'graph_action',
      label: ko.combat.flee,
      graphAction: { verb: 'move', how: 'flee' },
      textFallback: compose.flee(),
    },
    {
      kind: 'graph_action',
      label: ko.combat.persuade,
      graphAction: { verb: 'speak', to: targetId },
      textFallback: compose.persuade(target.name),
    },
  ];
}
