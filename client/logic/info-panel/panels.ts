import { joinOrDash } from '@/components/ui';
import { ko } from '@/locale/ko';
import { buildHeroSlot } from '@/logic/hero';
import type { Hero } from '@/logic/hero';
import type { Quest } from '@/logic/quest';
import type { Subject } from '@/logic/subject';

import type { Panel, PanelAction, PanelActions, PanelSlot } from './types';

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
  return [
    buildNotesSlot(state, { dot: opts?.questDot || opts?.subjectDot }),
    buildHeroSlot(state.hero, { chipShort: ko.table.sheet }),
  ];
}

function buildNotesSlot(state: GameSnapshot, opts?: { dot?: boolean }): PanelSlot {
  const panel = buildNotesPanel(state);
  return {
    id: 'notes',
    chip: { short: ko.table.notes, dot: opts?.dot },
    panel,
  };
}

function buildNotesPanel(state: GameSnapshot): Panel {
  const sections: NonNullable<Panel['sections']> = [];
  const actions: PanelActions[] = [];

  if (state.subject) {
    sections.push({
      label: ko.subject.chip,
      text: joinOrDash([
        state.subject.name,
        state.subject.role,
        ...state.subject.known,
      ]),
      clampLines: 3,
    });
  }

  const activeQuest = state.quest ?? null;
  const firstOffer = state.questOffers?.[0] ?? null;
  if (activeQuest) {
    sections.push(
      { label: ko.panel.goal, text: joinOrDash(activeQuest.goals), clampLines: 2 },
      { label: ko.panel.summary, text: activeQuest.summary, clampLines: 3 },
    );
    const questActions = questActionItems(activeQuest);
    if (questActions.length > 0) {
      actions.push({ label: ko.quest.name, items: questActions });
    }
  } else if (firstOffer) {
    sections.push(
      { label: ko.quest.offer, text: firstOffer.title, clampLines: 1 },
      { label: ko.panel.summary, text: firstOffer.summary, clampLines: 3 },
    );
    const offerActions = questActionItems(firstOffer).filter((action) => action.label === ko.quest.accept);
    if (offerActions.length > 0) {
      actions.push({ label: ko.quest.offer, items: offerActions });
    }
  }

  if (sections.length === 0) {
    return { empty: true, title: ko.table.notes, sections: [{ label: ko.panel.summary, text: ko.table.noNotes }] };
  }

  return {
    title: ko.table.notes,
    sections,
    actions: actions.length > 0 ? actions : undefined,
  };
}

function questActionItems(quest: Quest): PanelAction[] {
  return quest.actions.map((kind) => ({
    kind: 'quest_action' as const,
    label: kind === 'accept' ? ko.quest.accept : ko.quest.abandon,
    questAction: { kind, quest_id: quest.id },
  }));
}
