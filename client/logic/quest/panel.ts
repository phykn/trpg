import { joinOrDash } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { MetaSegment, PanelAction, PanelActions, PanelSlot } from '@/logic/info-panel';

import type { Quest } from './types';

const ACTION_LABEL: Record<'accept' | 'abandon', string> = {
  accept: ko.quest.accept,
  abandon: ko.quest.abandon,
};

export function buildQuestSlot(quest: Quest | null, opts?: { dot?: boolean }): PanelSlot {
  if (!quest) {
    return {
      id: 'quest',
      chip: { short: ko.quest.name, dot: opts?.dot },
      panel: { empty: true, title: ko.quest.name },
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
  }));
  const actions: PanelActions[] = actionItems.length > 0
    ? [{ label: ko.quest.name, items: actionItems }]
    : [];
  return {
    id: 'quest',
    chip: { short: ko.quest.name, dot: opts?.dot },
    panel: {
      title: quest.title,
      meta,
      sections: [
        { label: ko.panel.goal, text: joinOrDash(quest.goals) },
        { label: ko.panel.summary, text: quest.summary },
        { label: ko.panel.reward, nodes: [['GOLD', quest.rewards.gold], ['EXP', quest.rewards.exp]] },
        { label: ko.panel.commission, text: quest.giver },
      ],
      actions: actions.length > 0 ? actions : undefined,
    },
  };
}
