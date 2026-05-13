import { compose, ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import type { CombatBadge } from './types';

export function buildCombatActions(combat: CombatBadge): PanelAction[] {
  const target = combat.enemies.find((enemy) => enemy.alive);
  if (!target) return [];
  const targetId = typeof target.id === 'string' && target.id ? target.id : target.name;
  return [
    {
      kind: 'combat_command',
      label: ko.combat.attack,
      combatCommand: { command: 'attack', target_id: targetId },
      textFallback: compose.attack(target.name),
    },
    {
      kind: 'combat_command',
      label: ko.combat.skill,
      combatCommand: { command: 'skill', target_id: targetId },
      textFallback: ko.combat.skillFallback,
    },
    {
      kind: 'combat_command',
      label: ko.combat.defend,
      combatCommand: { command: 'defend' },
      textFallback: compose.defend(),
    },
    {
      kind: 'combat_command',
      label: ko.combat.flee,
      combatCommand: { command: 'flee' },
      textFallback: compose.flee(),
    },
  ];
}
