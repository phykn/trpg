import { ko } from '@/locale/ko';
import type { CombatBadge } from '@/logic/combat/types';
import type { NarrationCue } from '@/logic/log/types';
import type { Quest } from '@/logic/quest/types';
import type { Place } from '@/logic/story-graph/types';
import type { Subject } from '@/logic/subject/types';

import type { DecisionStateItem, DecisionStateTone } from './types';

type BuildDecisionStateInput = {
  place: Place | null;
  quest: Quest | null;
  combat: CombatBadge | null;
  subject?: Subject | null;
  heroVitals?: {
    level: number;
    exp: number;
    expMax: number;
    hp: number;
    hpMax: number;
    mp: number;
    mpMax: number;
  };
  heroStatus: string[];
  latestCues: NarrationCue[];
  scenarioCompleted?: boolean;
};

const MAX_ITEMS = 7;

export function buildDecisionState(input: BuildDecisionStateInput): DecisionStateItem[] {
  const items: DecisionStateItem[] = [];

  if (input.heroVitals) {
    items.push(
      {
        id: 'hero:level',
        label: 'LV',
        text: `${input.heroVitals.level}`,
        tone: 'level',
        progress: progressRatio(input.heroVitals.exp, input.heroVitals.expMax),
      },
      {
        id: 'hero:hp',
        label: 'HP',
        text: `${input.heroVitals.hp}/${input.heroVitals.hpMax}`,
        tone: 'hp',
      },
      {
        id: 'hero:mp',
        label: 'MP',
        text: `${input.heroVitals.mp}/${input.heroVitals.mpMax}`,
        tone: 'mp',
      },
    );
  }

  if (input.place) {
    items.push({
      id: 'place',
      label: '',
      text: input.place.name,
      tone: 'neutral',
    });
  }

  const facedName = facedSubjectName(input.combat, input.subject ?? null);
  if (facedName) {
    items.push({
      id: 'subject:faced',
      label: '',
      text: facedName,
      tone: 'accent',
    });
  }

  if (input.scenarioCompleted) {
    items.push({
      id: 'scenario:completed',
      label: '',
      text: ko.quest.completed,
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

function progressRatio(value: number, max: number): number {
  if (max <= 0) return 0;
  return Math.max(0, Math.min(1, value / max));
}

function facedSubjectName(combat: CombatBadge | null, subject: Subject | null): string | null {
  const enemy = combat?.enemies.find((it) => it.alive) ?? combat?.enemies[0] ?? null;
  if (enemy) return enemy.name;
  return subject?.alive ? subject.name : null;
}
