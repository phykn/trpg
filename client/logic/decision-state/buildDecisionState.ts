import { ko } from '@/locale/ko';
import type { CombatBadge } from '@/logic/combat/types';
import type { NarrationCue } from '@/logic/log/types';
import type { Quest } from '@/logic/quest/types';
import type { Place } from '@/logic/story-graph/types';

import type { DecisionStateItem, DecisionStateTone } from './types';

type BuildDecisionStateInput = {
  place: Place | null;
  quest: Quest | null;
  combat: CombatBadge | null;
  heroStatus: string[];
  latestCues: NarrationCue[];
  scenarioCompleted?: boolean;
};

const MAX_ITEMS = 5;
const COMPACT_TEXT_MAX_CHARS = 15;

export function buildDecisionState(input: BuildDecisionStateInput): DecisionStateItem[] {
  const items: DecisionStateItem[] = [];

  if (input.place) {
    items.push({
      id: 'place',
      label: '',
      text: compactText(input.place.name),
      tone: 'neutral',
    });
  }

  if (input.quest?.status === 'active' && input.quest.goals[0]) {
    items.push({
      id: `quest:${input.quest.id}:goal`,
      label: '',
      text: compactText(input.quest.goals[0]),
      tone: 'accent',
    });
  } else if (input.scenarioCompleted) {
    items.push({
      id: 'scenario:completed',
      label: '',
      text: compactText(ko.quest.completed),
      tone: 'accent',
    });
  }

  if (input.combat) {
    items.push({
      id: 'combat:risk',
      label: ko.decision.risk,
      text: input.combat.turnLabel,
      tone: input.combat.enemyPressure > 0 ? 'danger' : 'warning',
    });
  }

  input.heroStatus.slice(0, 2).forEach((status, index) => {
    items.push({
      id: `status:${index}`,
      label: ko.decision.status,
      text: status,
      tone: 'warning',
    });
  });

  input.latestCues.filter((cue) => cue.scope === 'temporary').forEach((cue, index) => {
    items.push({
      id: `cue:${index}`,
      label: ko.decision.temporary,
      text: cue.text,
      tone: cueTone(cue),
      temporary: true,
    });
  });

  return items.slice(0, MAX_ITEMS);
}

function cueTone(cue: NarrationCue): DecisionStateTone {
  return cue.kind === 'warning' ? 'danger' : 'accent';
}

function compactText(value: string): string {
  return value.length > COMPACT_TEXT_MAX_CHARS
    ? `${value.slice(0, COMPACT_TEXT_MAX_CHARS)}...`
    : value;
}
