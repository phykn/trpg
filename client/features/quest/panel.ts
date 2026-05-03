import { joinOrDash } from '@/components/ui';
import type { PanelSlot } from '@/features/info-panel';

import type { Quest } from './types';

export function buildQuestSlot(quest: Quest | null, opts?: { dot?: boolean }): PanelSlot {
  if (!quest) {
    return {
      id: 'quest',
      chip: { short: '퀘스트', dot: opts?.dot },
      panel: { empty: true, title: '퀘스트' },
    };
  }
  return {
    id: 'quest',
    chip: { short: '퀘스트', dot: opts?.dot },
    panel: {
      title: quest.title,
      meta: [{ text: quest.difficulty.label, tone: quest.difficulty.tone ?? undefined }],
      sections: [
        { label: '의뢰', text: quest.giver },
        { label: '보상', nodes: [['GOLD', quest.rewards.gold], ['EXP', quest.rewards.exp]] },
        { label: '목표', text: joinOrDash(quest.goals) },
        { label: '조건', text: joinOrDash(quest.conditions) },
        { label: '요약', text: quest.summary },
      ],
    },
  };
}
