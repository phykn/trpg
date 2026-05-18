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
};

const MAX_ITEMS = 5;

export function buildDecisionState(input: BuildDecisionStateInput): DecisionStateItem[] {
  const items: DecisionStateItem[] = [];

  if (input.place) {
    items.push({
      id: 'place',
      label: ko.decision.place,
      text: input.place.name,
      tone: 'neutral',
    });
  }

  if (input.quest?.status === 'active' && input.quest.goals[0]) {
    items.push({
      id: `quest:${input.quest.id}:goal`,
      label: ko.decision.goal,
      text: input.quest.goals[0],
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
