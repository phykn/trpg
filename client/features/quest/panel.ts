import { joinOrDash } from '@/components/ui';
import type { MetaSegment, PanelSlot } from '@/features/info-panel';

import type { Quest } from './types';

export function buildQuestSlot(quest: Quest | null, opts?: { dot?: boolean }): PanelSlot {
  if (!quest) {
    return {
      id: 'quest',
      chip: { short: '퀘스트', dot: opts?.dot },
      panel: { empty: true, title: '퀘스트' },
    };
  }
  const meta: MetaSegment[] = [
    { text: quest.difficulty.label, tone: quest.difficulty.tone ?? undefined },
  ];
  if (quest.progressLabel) {
    meta.push({ text: ` · ${quest.progressLabel}` });
  }
  return {
    id: 'quest',
    chip: { short: '퀘스트', dot: opts?.dot },
    panel: {
      title: quest.title,
      meta,
      sections: [
        { label: '목표', text: joinOrDash(quest.goals) },
        { label: '요약', text: quest.summary },
        { label: '보상', nodes: [['GOLD', quest.rewards.gold], ['EXP', quest.rewards.exp]] },
        { label: '의뢰', text: quest.giver },
        { label: '조건', text: joinOrDash(quest.conditions) },
      ],
    },
  };
}
