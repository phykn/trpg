import { compose, ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import type { CombatBadge, CombatSupport } from './types';

type Target = {
  id: string;
  name: string;
};

export function buildCombatActions(combat: CombatBadge): PanelAction[] {
  const target = activeTarget(combat);
  if (!target) return [];

  const attack = supportAction(combat, 'attack', target)
    ?? plainAttack(target);
  const defend = supportAction(combat, 'defend', target)
    ?? plainDefend();
  const situation = situationAction(combat, target);

  return [attack, defend, situation].slice(0, 3);
}

function activeTarget(combat: CombatBadge): Target | null {
  const target = combat.enemies.find((enemy) => enemy.alive);
  if (!target) return null;
  const id = typeof target.id === 'string' && target.id ? target.id : target.name;
  return { id, name: target.name };
}

function situationAction(combat: CombatBadge, target: Target): PanelAction {
  if (combat.escapeReady) return plainCreateDistance(ko.combat.escape, compose.escape());

  const escapeSupport = supportAction(combat, 'flee', target);
  if (escapeSupport) return escapeSupport;

  if (combat.enemyPressure > 0 || combat.enemyHearts.current <= 1) {
    return plainTalk(target);
  }

  return plainCreateDistance(ko.combat.flee, compose.flee());
}

function supportAction(
  combat: CombatBadge,
  action: CombatSupport['action'],
  target: Target,
): PanelAction | null {
  const support = combat.availableSupports.find(
    (candidate) => candidate.usable && candidate.action === action,
  );
  if (!support) return null;
  return {
    kind: 'combat_command',
    label: support.name,
    combatCommand: {
      ...commandForAction(action, target),
      support_id: support.id,
      support_kind: 'skill',
    },
    textFallback: compose.useSkill(support.name),
  };
}

function commandForAction(
  action: CombatSupport['action'],
  target: Target,
): Extract<PanelAction, { kind: 'combat_command' }>['combatCommand'] {
  if (action === 'attack') return { command: 'attack', target: target.id };
  if (action === 'talk') return { command: 'talk', target: target.id };
  if (action === 'defend') return { command: 'defend' };
  return { command: 'flee' };
}

function plainAttack(target: Target): PanelAction {
  return {
    kind: 'combat_command',
    label: ko.combat.attack,
    combatCommand: { command: 'attack', target: target.id },
    textFallback: compose.attack(target.name),
  };
}

function plainDefend(): PanelAction {
  return {
    kind: 'combat_command',
    label: ko.combat.defend,
    combatCommand: { command: 'defend' },
    textFallback: compose.defend(),
  };
}

function plainCreateDistance(label: string, textFallback: string): PanelAction {
  return {
    kind: 'combat_command',
    label,
    combatCommand: { command: 'flee' },
    textFallback,
  };
}

function plainTalk(target: Target): PanelAction {
  return {
    kind: 'combat_command',
    label: ko.combat.talk,
    combatCommand: { command: 'talk', target: target.id },
    textFallback: compose.talkTo(target.name),
  };
}
