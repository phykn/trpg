import { buildHeroSlot } from '@/logic/hero';
import type { Hero } from '@/logic/hero';
import { buildQuestOfferSlot, buildQuestSlot } from '@/logic/quest';
import type { Quest } from '@/logic/quest';
import { buildSubjectSlot } from '@/logic/subject';
import type { Subject } from '@/logic/subject';

import type { PanelSlot } from './types';

type GameSnapshot = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
  questOffers?: Quest[];
};

type BuildPanelSlotsOpts = {
  questDot?: boolean;
  subjectDot?: boolean;
};

export function buildPanelSlots(
  state: GameSnapshot,
  opts?: BuildPanelSlotsOpts,
): PanelSlot[] {
  const questSlots: PanelSlot[] = [];
  const firstOffer = state.questOffers?.[0] ?? null;
  if (state.quest) {
    questSlots.push(buildQuestSlot(state.quest, { dot: opts?.questDot }));
    if (firstOffer) {
      questSlots.push(buildQuestOfferSlot(firstOffer, { dot: opts?.questDot }));
    }
  } else if (firstOffer) {
    questSlots.push(buildQuestOfferSlot(firstOffer, { dot: opts?.questDot }));
  } else {
    questSlots.push(buildQuestSlot(null, { dot: opts?.questDot }));
  }

  return [
    buildHeroSlot(state.hero),
    buildSubjectSlot(state.subject, { dot: opts?.subjectDot }),
    ...questSlots,
  ];
}
