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

export function buildPanelSlots(state: GameSnapshot): PanelSlot[] {
  return [
    buildHeroSlot(state.hero),
    buildSubjectSlot(state.subject),
    buildQuestSlot(state.quest),
  ];
}
