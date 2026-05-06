import { buildHeroSlot } from '@/logic/hero';
import type { Hero } from '@/logic/hero';
import { buildQuestSlot } from '@/logic/quest';
import type { Quest } from '@/logic/quest';
import { buildSubjectSlot } from '@/logic/subject';
import type { Subject } from '@/logic/subject';

import type { PanelSlot } from './types';

type GameSnapshot = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
};

type BuildPanelSlotsOpts = {
  onLevelUpOpen?: () => void;
  questDot?: boolean;
  subjectDot?: boolean;
};

export function buildPanelSlots(
  state: GameSnapshot,
  opts?: BuildPanelSlotsOpts,
): PanelSlot[] {
  return [
    buildHeroSlot(state.hero, { onLevelUpOpen: opts?.onLevelUpOpen }),
    buildSubjectSlot(state.subject, { dot: opts?.subjectDot }),
    buildQuestSlot(state.quest, { dot: opts?.questDot }),
  ];
}
