import { ko } from '@/locale/ko';
import type { Discoveries, DiscoveryEntry } from '@/logic/discoveries';
import { buildHeroSlot } from '@/logic/hero';
import type { Hero } from '@/logic/hero';
import type { Quest } from '@/logic/quest';
import type { Subject } from '@/logic/subject';

import type { Panel, PanelSlot } from './types';

type GameSnapshot = {
  hero: Hero;
  subject: Subject | null;
  chapter?: { title: string; summary: string } | null;
  discoveries?: Discoveries;
  slotDots?: Partial<Record<'hero' | 'notes', boolean>>;
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
      chip: { ...heroSlot.chip, dot: state.slotDots?.hero ?? false },
      panel: heroSlot.panel ? { ...heroSlot.panel, title: '', meta: undefined, barSplit: undefined } : null,
    },
    buildInfoSlot(state),
  ];
}

function buildInfoSlot(state: GameSnapshot): PanelSlot {
  return {
    id: 'notes',
    chip: { short: ko.quest.chapter, dot: state.slotDots?.notes ?? false },
    panel: withoutHeader(buildNotesPanel(state)),
  };
}

function withoutHeader(panel: Panel): Panel {
  return { ...panel, title: '', meta: undefined };
}

function buildDiscoverySections(discoveries: Discoveries | undefined): NonNullable<Panel['sections']> {
  if (!discoveries) return [];
  const sections = dedupeSections([
    ...discoverySections(ko.discoveries.clues, discoveries.clues),
    ...discoverySections(ko.discoveries.memories, discoveries.memories),
  ]);
  return sections;
}

function dedupeSections(sections: NonNullable<Panel['sections']>): NonNullable<Panel['sections']> {
  const seen = new Set<string>();
  return sections.filter((section) => {
    const key = section.text ?? section.label;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function discoverySections(kindLabel: string, entries: DiscoveryEntry[]): NonNullable<Panel['sections']> {
  return entries.map((entry) => ({
    label: kindLabel,
    text: discoveryText(entry),
    clampLines: 3,
  }));
}

function discoveryText(entry: DiscoveryEntry): string {
  if (entry.summary && entry.summary !== entry.title) {
    return `${entry.title}\n${entry.summary}`;
  }
  return entry.title;
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
    if (state.chapter.summary) {
      sections.push({ label: ko.panel.summary, text: state.chapter.summary, clampLines: 3 });
    }
  }
  if (!state.chapter && activeQuest?.summary) {
    sections.push({ label: ko.panel.summary, text: activeQuest.summary, clampLines: 3 });
  } else if (!state.chapter && firstOffer) {
    sections.push(
      { label: ko.quest.offer, text: firstOffer.title, clampLines: 1 },
      { label: ko.panel.summary, text: firstOffer.summary, clampLines: 3 },
    );
  } else if (!state.chapter && state.scenarioCompleted) {
    sections.push({ label: ko.panel.summary, text: ko.gameOver.ending, clampLines: 2 });
  }

  sections.push(...buildDiscoverySections(state.discoveries));

  if (sections.length === 0) {
    return { empty: true, title: ko.table.info, sections: [{ label: ko.panel.summary, text: ko.table.noNotes }] };
  }

  return {
    title: ko.table.info,
    sections,
  };
}
