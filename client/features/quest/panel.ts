import { joinOrDash } from '@/components/ui';
import type { MetaSegment, PanelAction, PanelActions, PanelSlot } from '@/features/info-panel';

import type { Quest } from './types';

const ACTION_LABEL: Record<'accept' | 'abandon', string> = {
  accept: '수락',
  abandon: '포기',
};

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
  const actionItems: PanelAction[] = quest.actions.map((kind) => ({
    kind: 'quest_action' as const,
    label: ACTION_LABEL[kind],
    questAction: { kind, quest_id: quest.id },
    ...(kind === 'abandon'
      ? { confirm: { title: '퀘스트 포기', blurb: '진행 상황이 사라집니다.', confirmLabel: '포기' } }
      : {}),
  }));
  const actions: PanelActions[] = actionItems.length > 0
    ? [{ label: '퀘스트', items: actionItems }]
    : [];
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
      actions: actions.length > 0 ? actions : undefined,
    },
  };
}
