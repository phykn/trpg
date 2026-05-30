import React from 'react';

import type { Discoveries } from '@/logic/discoveries';
import type { Hero } from '@/logic/hero';
import type { Quest } from '@/logic/quest';

export type TopPanelSlotId = 'hero' | 'notes';
export type PanelSlotContentKeys = Record<TopPanelSlotId, string>;
export type PanelSlotDots = Record<TopPanelSlotId, boolean>;

export type PanelSlotTrackingSource = {
  gameId: string | null;
  hero: Hero | null;
  chapter?: { title: string; summary: string } | null;
  quest: Quest | null;
  questOffers?: Quest[];
  discoveries: Discoveries;
  scenarioCompleted?: boolean;
};

export function buildPanelSlotContentKeys(source: PanelSlotTrackingSource): PanelSlotContentKeys {
  return {
    hero: JSON.stringify(source.hero ?? null),
    notes: JSON.stringify({
      chapter: source.chapter,
      discoveries: source.discoveries,
      scenarioCompleted: source.scenarioCompleted,
      quest: source.quest,
      questOffers: source.questOffers,
    }),
  };
}

export function buildPanelSlotDots(
  activeId: string | null,
  seenSlotKeys: PanelSlotContentKeys,
  currentSlotKeys: PanelSlotContentKeys,
): PanelSlotDots {
  return {
    hero: activeId !== 'hero' && seenSlotKeys.hero !== currentSlotKeys.hero,
    notes: activeId !== 'notes' && seenSlotKeys.notes !== currentSlotKeys.notes,
  };
}

export function isTopPanelSlotId(id: string | null): id is TopPanelSlotId {
  return id === 'hero' || id === 'notes';
}

export function usePanelSlotTracking(source: PanelSlotTrackingSource, activeId: string | null) {
  const gameIdRef = React.useRef(source.gameId);
  const currentSlotKeys = React.useMemo(
    () => buildPanelSlotContentKeys(source),
    [
      source.chapter,
      source.discoveries,
      source.hero,
      source.quest,
      source.questOffers,
      source.scenarioCompleted,
    ],
  );
  const [seenSlotKeys, setSeenSlotKeys] = React.useState<PanelSlotContentKeys>(() => currentSlotKeys);

  React.useEffect(() => {
    if (gameIdRef.current === source.gameId) return;
    gameIdRef.current = source.gameId;
    setSeenSlotKeys(currentSlotKeys);
  }, [currentSlotKeys, source.gameId]);

  const markSlotSeen = React.useCallback((id: string | null) => {
    if (!isTopPanelSlotId(id)) return;
    setSeenSlotKeys((prev) => (
      prev[id] === currentSlotKeys[id]
        ? prev
        : { ...prev, [id]: currentSlotKeys[id] }
    ));
  }, [currentSlotKeys]);

  React.useEffect(() => {
    markSlotSeen(activeId);
  }, [activeId, markSlotSeen]);

  const slotDots = React.useMemo(
    () => buildPanelSlotDots(activeId, seenSlotKeys, currentSlotKeys),
    [activeId, currentSlotKeys, seenSlotKeys],
  );

  return { slotDots, markSlotSeen };
}
