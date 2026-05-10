import React from 'react';

import {
  EMPTY_STORY_GRAPH,
  isValidStoryGraph,
  mergeStoryGraphs,
  storyGraphFingerprint,
} from './presenters';
import type { StoryGraphModel } from './types';
import { getStorage, loadSeenNodes, storeSeenNodes } from '@/services/storage';

// Hydrate the seen-node set from cache and auto-seed with the player's starting
// place node so it doesn't get a "new" ring on first load.
export function loadAndSeedSeenNodes(gameId: string, graph: StoryGraphModel): Set<string> {
  const loaded = loadSeenNodes(gameId);
  const startNode = graph.nodes.find((n) => n.kind === 'place');
  if (startNode && !loaded.has(startNode.id)) {
    loaded.add(startNode.id);
    storeSeenNodes(gameId, loaded);
  }
  return loaded;
}

const STORAGE_PREFIX = 'trpg.story_graph.';
export const STORY_GRAPH_UPDATED_EVENT = 'trpg:story-graph-updated';
type StoryGraphEventWindow = {
  addEventListener?: Window['addEventListener'];
  removeEventListener?: Window['removeEventListener'];
  dispatchEvent?: Window['dispatchEvent'];
};

export function readStoredStoryGraph(gameId: string): StoryGraphModel | null {
  const raw = getStorage()?.getItem(`${STORAGE_PREFIX}${gameId}`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return isValidStoryGraph(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function writeStoredStoryGraph(gameId: string, graph: StoryGraphModel): void {
  // Best-effort cache. localStorage can throw QuotaExceededError after many games
  // pile up; swallow it rather than crashing the render tree — server stays authoritative.
  try {
    getStorage()?.setItem(`${STORAGE_PREFIX}${gameId}`, JSON.stringify(graph));
  } catch {
    // intentionally empty
  }
}

export function mergeAndStoreStoryGraph(gameId: string, current: StoryGraphModel): StoryGraphModel {
  const next = mergeStoryGraphs(readStoredStoryGraph(gameId) ?? EMPTY_STORY_GRAPH, current);
  writeStoredStoryGraph(gameId, next);
  dispatchStoryGraphUpdated(gameId);
  return next;
}

export function dispatchStoryGraphUpdated(gameId: string): void {
  const target = storyGraphEventWindow();
  if (!target?.dispatchEvent) return;
  const event = createStoryGraphUpdatedEvent(gameId);
  if (!event) return;
  target.dispatchEvent(event);
}

export function subscribeStoryGraphUpdates(
  onUpdate: (gameId: string) => void,
): () => void {
  const target = storyGraphEventWindow();
  if (!target?.addEventListener || !target.removeEventListener) return () => {};
  const listener = (event: Event) => {
    const gameId = storyGraphUpdatedGameId(event);
    if (gameId) onUpdate(gameId);
  };
  target.addEventListener(STORY_GRAPH_UPDATED_EVENT, listener);
  return () => target.removeEventListener?.(STORY_GRAPH_UPDATED_EVENT, listener);
}

function storyGraphEventWindow(): StoryGraphEventWindow | null {
  return typeof window === 'undefined' ? null : window;
}

function createStoryGraphUpdatedEvent(gameId: string): Event | null {
  const detail = { gameId };
  if (typeof CustomEvent === 'function') {
    return new CustomEvent(STORY_GRAPH_UPDATED_EVENT, { detail });
  }
  if (typeof Event !== 'function') return null;
  const event = new Event(STORY_GRAPH_UPDATED_EVENT);
  Object.defineProperty(event, 'detail', { value: detail });
  return event;
}

function storyGraphUpdatedGameId(event: Event): string | null {
  const detail = (event as Event & { detail?: { gameId?: unknown } }).detail;
  return typeof detail?.gameId === 'string' ? detail.gameId : null;
}

type StoryGraphHookValue = {
  graph: StoryGraphModel;
  unseenNodeIds: Set<string>;
  markNodeSeen: (id: string) => void;
};

export function useStoryGraph(gameId: string | null, current: StoryGraphModel): StoryGraphHookValue {
  const [graph, setGraph] = React.useState<StoryGraphModel>(current);
  const [seen, setSeen] = React.useState<Set<string>>(() => new Set());
  const activeGameId = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!gameId) {
      activeGameId.current = null;
      setGraph(current.nodes.length > 0 ? current : EMPTY_STORY_GRAPH);
      setSeen(new Set());
      return;
    }

    if (activeGameId.current !== gameId) {
      activeGameId.current = gameId;
      const next = mergeStoryGraphs(readStoredStoryGraph(gameId) ?? EMPTY_STORY_GRAPH, current);
      setGraph(next);
      writeStoredStoryGraph(gameId, next);
      setSeen(loadAndSeedSeenNodes(gameId, next));
      return;
    }

    setGraph((previous) => {
      const next = mergeStoryGraphs(previous, current);
      if (storyGraphFingerprint(previous) === storyGraphFingerprint(next)) return previous;
      writeStoredStoryGraph(gameId, next);
      return next;
    });
  }, [current, gameId]);

  const unseenNodeIds = React.useMemo(() => {
    const out = new Set<string>();
    for (const n of graph.nodes) if (!seen.has(n.id)) out.add(n.id);
    return out;
  }, [graph, seen]);

  const markNodeSeen = React.useCallback(
    (id: string) => {
      const activeId = activeGameId.current;
      if (!activeId || seen.has(id)) return;
      setSeen((prev) => {
        const next = new Set(prev);
        next.add(id);
        storeSeenNodes(activeId, next);
        return next;
      });
    },
    [seen],
  );

  return { graph, unseenNodeIds, markNodeSeen };
}
