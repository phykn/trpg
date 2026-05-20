import { ko } from '@/locale/ko';
import { buildHeroSlot } from '@/logic/hero';
import type { Hero } from '@/logic/hero';
import type { Quest } from '@/logic/quest';
import type { Subject } from '@/logic/subject';

import type { Panel, PanelSlot } from './types';

type GameSnapshot = {
  hero: Hero;
  subject: Subject | null;
  chapter?: { title: string; summary: string } | null;
  scenarioCompleted?: boolean;
  quest: Quest | null;
  questOffers?: Quest[];
};

export function buildPanelSlots(
  state: GameSnapshot,
): PanelSlot[] {
  const heroSlot = buildHeroSlot(state.hero, { chipShort: state.hero.name });
  return [
    {
      ...heroSlot,
      panel: heroSlot.panel ? { ...heroSlot.panel, title: '', meta: undefined, barSplit: undefined } : null,
    },
    buildInfoSlot(state),
  ];
}

function buildInfoSlot(state: GameSnapshot): PanelSlot {
  return {
    id: 'notes',
    chip: { short: ko.quest.chapter },
    panel: withoutHeader(buildNotesPanel(state)),
  };
}

function withoutHeader(panel: Panel): Panel {
  return { ...panel, title: '', meta: undefined };
}

function buildNotesPanel(state: GameSnapshot): Panel {
  const sections: NonNullable<Panel['sections']> = [];

  const activeQuest = state.quest ?? null;
  const firstOffer = state.questOffers?.[0] ?? null;
  if (state.chapter) {
    sections.push({
      label: ko.quest.chapter,
      text: state.chapter.title,
      clampLines: 1,
    });
  }
  if (activeQuest) {
    sections.push({ label: ko.panel.summary, text: activeQuest.summary, clampLines: 3 });
  } else if (firstOffer) {
    sections.push(
      { label: ko.quest.offer, text: firstOffer.title, clampLines: 1 },
      { label: ko.panel.summary, text: firstOffer.summary, clampLines: 3 },
    );
  } else if (state.scenarioCompleted) {
    sections.push({ label: ko.panel.summary, text: ko.gameOver.ending, clampLines: 2 });
  }

  if (sections.length === 0) {
    return { empty: true, title: ko.table.info, sections: [{ label: ko.panel.summary, text: ko.table.noNotes }] };
  }

  return {
    title: ko.table.info,
    sections,
  };
}
