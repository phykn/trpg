import { buildHeroSlot } from '@/features/hero';
import type { Hero } from '@/features/hero';
import { buildQuestSlot } from '@/features/quest';
import type { Quest } from '@/features/quest';
import { buildSubjectSlot } from '@/features/subject';
import type { Subject } from '@/features/subject';

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
