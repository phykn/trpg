import React from 'react';

import {
  EMPTY_STORY_GRAPH,
  isValidStoryGraph,
  mergeStoryGraphs,
  storyGraphFingerprint,
  type StoryGraphModel,
} from '@/presenters/storyGraph';
import { getStorage } from '@/services/storage';

const STORAGE_PREFIX = 'trpg.story_graph.';
export const STORY_GRAPH_UPDATED_EVENT = 'trpg:story-graph-updated';

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
  getStorage()?.setItem(`${STORAGE_PREFIX}${gameId}`, JSON.stringify(graph));
}

export function mergeAndStoreStoryGraph(gameId: string, current: StoryGraphModel): StoryGraphModel {
  const next = mergeStoryGraphs(readStoredStoryGraph(gameId) ?? EMPTY_STORY_GRAPH, current);
  writeStoredStoryGraph(gameId, next);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(STORY_GRAPH_UPDATED_EVENT, { detail: { gameId } }));
  }
  return next;
}

export function useStoryGraph(gameId: string | null, current: StoryGraphModel): StoryGraphModel {
  const [graph, setGraph] = React.useState<StoryGraphModel>(current);
  const activeGameId = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!gameId) {
      activeGameId.current = null;
      setGraph(current.nodes.length > 0 ? current : EMPTY_STORY_GRAPH);
      return;
    }

    if (activeGameId.current !== gameId) {
      activeGameId.current = gameId;
      const next = mergeStoryGraphs(readStoredStoryGraph(gameId) ?? EMPTY_STORY_GRAPH, current);
      setGraph(next);
      writeStoredStoryGraph(gameId, next);
      return;
    }

    setGraph((previous) => {
      const next = mergeStoryGraphs(previous, current);
      if (storyGraphFingerprint(previous) === storyGraphFingerprint(next)) return previous;
      writeStoredStoryGraph(gameId, next);
      return next;
    });
  }, [current, gameId]);

  return graph;
}
