import React from 'react';
import { ScrollView, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';
import { getGraphSessionById, loadStoredGameId, storeSeenNodes } from '@/services';

import { MapPanel } from './MapPanel';
import { EMPTY_STORY_GRAPH } from '@/logic/story-graph/presenters';
import type { StoryGraphModel } from '@/logic/story-graph/types';
import {
  loadAndSeedSeenNodes,
  mergeAndStoreStoryGraph,
  readStoredStoryGraph,
  STORY_GRAPH_UPDATED_EVENT,
} from '@/logic/story-graph/useStoryGraph';

type Status = 'loading' | 'ready' | 'empty' | 'error';

export function StoryGraphScreen({
  onAction,
}: {
  onAction: (action: PanelAction) => void;
}) {
  const [status, setStatus] = React.useState<Status>('loading');
  const gameIdRef = React.useRef<string | null>(null);
  const [graph, setGraph] = React.useState<StoryGraphModel>(EMPTY_STORY_GRAPH);
  const [message, setMessage] = React.useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);
  const [seen, setSeen] = React.useState<Set<string>>(() => new Set());

  React.useEffect(() => {
    let alive = true;
    (async () => {
      setStatus('loading');
      setMessage(null);
      const stored = loadStoredGameId();
      gameIdRef.current = stored;
      if (!stored) {
        setGraph(EMPTY_STORY_GRAPH);
        setStatus('empty');
        return;
      }
      try {
        const session = await getGraphSessionById(stored);
        if (!alive) return;
        if (!session) {
          setGraph(EMPTY_STORY_GRAPH);
          setStatus('empty');
          return;
        }
        const merged = mergeAndStoreStoryGraph(stored, session.state.storyGraph);
        setGraph(merged);
        setSeen(loadAndSeedSeenNodes(stored, merged));
        setStatus('ready');
      } catch (err) {
        if (!alive) return;
        setStatus('error');
        setMessage(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  React.useEffect(() => {
    if (status !== 'ready') return;
    if (selectedNodeId && graph.nodes.some((node) => node.id === selectedNodeId)) return;
    const currentPlace = graph.nodes.find((node) => node.kind === 'place');
    setSelectedNodeId(currentPlace ? currentPlace.id : null);
  }, [status, graph, selectedNodeId]);

  React.useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const onGraphUpdate = (event: Event) => {
      const detail = (event as CustomEvent<{ gameId?: string }>).detail;
      const updatedGameId = detail?.gameId;
      if (!updatedGameId || updatedGameId !== gameIdRef.current) return;
      setGraph(readStoredStoryGraph(updatedGameId) ?? EMPTY_STORY_GRAPH);
    };

    window.addEventListener(STORY_GRAPH_UPDATED_EVENT, onGraphUpdate);
    return () => window.removeEventListener(STORY_GRAPH_UPDATED_EVENT, onGraphUpdate);
  }, []);

  const unseenNodeIds = React.useMemo(() => {
    const out = new Set<string>();
    for (const n of graph.nodes) if (!seen.has(n.id)) out.add(n.id);
    return out;
  }, [graph, seen]);

  const markNodeSeen = React.useCallback(
    (id: string) => {
      const gameId = gameIdRef.current;
      if (!gameId || seen.has(id)) return;
      setSeen((prev) => {
        const next = new Set(prev);
        next.add(id);
        storeSeenNodes(gameId, next);
        return next;
      });
    },
    [seen],
  );

  return (
    <View className="flex-1 gap-2.5">
      <ScrollView
        className="flex-1"
        contentContainerStyle={{ gap: 10 }}
      >
        {message ? (
          <View className="rounded-sm border border-border-default bg-canvas-subtle px-3 py-2">
            <Text className="font-sans text-caption text-fg-muted">{message}</Text>
          </View>
        ) : null}

        {status === 'loading' ? (
          <View className="items-center justify-center py-14">
            <Text className="font-sans text-body text-fg-muted">{ko.panel.mapLoading}</Text>
          </View>
        ) : null}

        {status === 'empty' ? (
          <View className="items-center justify-center py-14 gap-3">
            <Text className="font-sans-semibold text-body text-fg-default">{ko.panel.noGame}</Text>
          </View>
        ) : null}

        {status === 'error' ? (
          <View className="rounded-sm border border-danger-fg bg-canvas-subtle px-3 py-2">
            <Text className="font-sans text-caption text-danger-fg">
              {message ?? ko.panel.mapError}
            </Text>
          </View>
        ) : null}

        {status === 'ready' ? (
          <MapPanel
            graph={graph}
            accessibilityLabel={ko.panel.fullMap}
            selectedNodeId={selectedNodeId}
            onNodeSelect={setSelectedNodeId}
            onAction={onAction}
            unseenNodeIds={unseenNodeIds}
            onNodeSeen={markNodeSeen}
          />
        ) : null}
      </ScrollView>
    </View>
  );
}
