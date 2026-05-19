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

  const precise = supportAction(combat, 'precise', target)
    ?? plainPrecise(target);
  const guarded = supportAction(combat, 'defend', target)
    ?? plainGuarded();
  const situation = situationAction(combat, target);

  return [precise, guarded, situation].slice(0, 3);
}

function activeTarget(combat: CombatBadge): Target | null {
  const target = combat.enemies.find((enemy) => enemy.alive);
  if (!target) return null;
  const id = typeof target.id === 'string' && target.id ? target.id : target.name;
  return { id, name: target.name };
}

function situationAction(combat: CombatBadge, target: Target): PanelAction {
  if (combat.escapeReady) return plainCreateDistance(ko.combat.escape, compose.escape());

  const escapeSupport = supportAction(combat, 'create_distance', target);
  if (escapeSupport) return escapeSupport;

  if (combat.enemyPressure > 0 || combat.enemyHearts.current <= 1) {
    return plainTalk(target);
  }

  const recklessSupport = supportAction(combat, 'reckless', target);
  if (recklessSupport) return recklessSupport;

  return plainCreateDistance(ko.combat.createDistance, compose.createDistance());
}

function supportAction(
  combat: CombatBadge,
  tactic: CombatSupport['tactic'],
  target: Target,
): PanelAction | null {
  const support = combat.availableSupports.find(
    (candidate) => candidate.usable && candidate.tactic === tactic,
  );
  if (!support) return null;
  return {
    kind: 'combat_command',
    label: support.name,
    combatCommand: {
      ...commandForTactic(tactic, target),
      support_id: support.id,
      support_kind: 'skill',
    },
    textFallback: compose.useSkill(support.name),
  };
}

function commandForTactic(
  tactic: CombatSupport['tactic'],
  target: Target,
): Extract<PanelAction, { kind: 'combat_command' }>['combatCommand'] {
  if (tactic === 'precise') return { command: 'precise', target: target.id };
  if (tactic === 'reckless') return { command: 'reckless', target: target.id };
  if (tactic === 'talk') return { command: 'talk', target: target.id };
  if (tactic === 'defend') return { command: 'defend' };
  if (tactic === 'guarded') return { command: 'guarded' };
  return { command: 'create_distance' };
}

function plainPrecise(target: Target): PanelAction {
  return {
    kind: 'combat_command',
    label: ko.combat.precise,
    combatCommand: { command: 'precise', target: target.id },
    textFallback: compose.preciseAttack(target.name),
  };
}

function plainGuarded(): PanelAction {
  return {
    kind: 'combat_command',
    label: ko.combat.guarded,
    combatCommand: { command: 'defend' },
    textFallback: compose.guarded(),
  };
}

function plainCreateDistance(label: string, textFallback: string): PanelAction {
  return {
    kind: 'combat_command',
    label,
    combatCommand: { command: 'create_distance' },
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
