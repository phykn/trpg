import { buildSubjectSlot, buildQuestSlot, buildPlaceSlot } from '@/services';
import type { Subject, Quest, Place, PanelSlot } from '@/types/game';

export function usePanels(subject: Subject | null, quest: Quest | null, place: Place): PanelSlot[] {
  return [
    buildSubjectSlot(subject),
    buildQuestSlot(quest),
    buildPlaceSlot(place),
  ];
}
