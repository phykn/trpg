import { useFocusEffect } from '@react-navigation/native';
import { router } from 'expo-router';
import React from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';

import { colors, shadow } from '@/design/tokens';
import {
  mergeAndStoreStoryGraph,
  readStoredStoryGraph,
  STORY_GRAPH_UPDATED_EVENT,
} from '@/hooks/useStoryGraph';
import {
  buildStoryGraph,
  EMPTY_STORY_GRAPH,
  normalizeStoryGraphPayload,
  type StoryGraphModel,
} from '@/presenters/storyGraph';
import {
  getSessionById,
  getSessionGraphById,
  loadStoredGameId,
  streamTurn,
} from '@/services';
import type { PanelAction } from '@/types/ui';
import type { StreamEvent } from '@/types/wire';

import { StoryGraphPanel } from './StoryGraphPanel';

type Status = 'loading' | 'ready' | 'empty' | 'error';
type Source = 'backend' | 'front-state';

const SOURCE_LABEL: Record<Source, string> = {
  backend: 'API',
  'front-state': 'STATE',
};

export function StoryGraphScreen() {
  const [status, setStatus] = React.useState<Status>('loading');
  const gameIdRef = React.useRef<string | null>(null);
  const [graph, setGraph] = React.useState<StoryGraphModel>(EMPTY_STORY_GRAPH);
  const [source, setSource] = React.useState<Source>('front-state');
  const [message, setMessage] = React.useState<string | null>(null);
  const [actionMessage, setActionMessage] = React.useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);
  const [actionRunning, setActionRunning] = React.useState(false);
  const actionAbortRef = React.useRef<AbortController | null>(null);

  const loadGraph = React.useCallback(async (isAlive: () => boolean) => {
    setStatus('loading');
    setMessage(null);
    setActionMessage(null);
    const stored = loadStoredGameId();
    gameIdRef.current = stored;
    if (!stored) {
      setGraph(EMPTY_STORY_GRAPH);
      setStatus('empty');
      return;
    }

    try {
      const graphPayload = await getSessionGraphById(stored);
      const normalizedGraph = normalizeStoryGraphPayload(graphPayload);
      if (!isAlive()) return;
      if (normalizedGraph) {
        setGraph(normalizedGraph);
        setSource('backend');
        setStatus('ready');
        return;
      }

      const session = await getSessionById(stored);
      if (!isAlive()) return;
      if (!session) {
        setGraph(EMPTY_STORY_GRAPH);
        setStatus('empty');
        return;
      }

      setGraph(mergeAndStoreStoryGraph(stored, buildStoryGraph(session.state)));
      setSource('front-state');
      setMessage(
        graphPayload
          ? '서버 graph 응답을 그래프 모델로 읽을 수 없어 현재 state로 표시합니다.'
          : '서버 graph endpoint가 없어 현재 state로 표시합니다.',
      );
      setStatus('ready');
    } catch (err) {
      if (!isAlive()) return;
      setStatus('error');
      setMessage(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useFocusEffect(
    React.useCallback(() => {
      let alive = true;
      void loadGraph(() => alive);
      return () => {
        alive = false;
      };
    }, [loadGraph]),
  );

  React.useEffect(() => {
    if (selectedNodeId && !graph.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(null);
    }
  }, [graph.nodes, selectedNodeId]);

  React.useEffect(() => {
    return () => {
      actionAbortRef.current?.abort();
    };
  }, []);

  const handleActionEvent = React.useCallback((ev: StreamEvent) => {
    if (ev.type === 'state') {
      const stored = gameIdRef.current;
      if (!stored) return;
      setGraph(mergeAndStoreStoryGraph(stored, buildStoryGraph(ev.data)));
      setSource('front-state');
      setSelectedNodeId(null);
      setActionMessage('지도 명령 결과를 반영했습니다.');
      return;
    }
    if (ev.type === 'pending_check') {
      setActionMessage('판정이 필요합니다. 게임 화면으로 돌아가 주사위를 굴려주세요.');
      return;
    }
    if (ev.type === 'error') {
      setActionMessage(ev.data.message);
    }
  }, []);

  const runMapAction = React.useCallback(async (action: PanelAction) => {
    const stored = gameIdRef.current;
    if (!stored || actionRunning) return;
    actionAbortRef.current?.abort();
    const controller = new AbortController();
    actionAbortRef.current = controller;
    setActionRunning(true);
    setActionMessage(`${action.intent} 처리 중입니다.`);
    try {
      await streamTurn(stored, { player_input: action.intent, think: false }, handleActionEvent, controller.signal);
    } catch (err) {
      if (!controller.signal.aborted) {
        setActionMessage(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (actionAbortRef.current === controller) actionAbortRef.current = null;
      setActionRunning(false);
    }
  }, [actionRunning, handleActionEvent]);

  React.useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const onGraphUpdate = (event: Event) => {
      const detail = (event as CustomEvent<{ gameId?: string }>).detail;
      const updatedGameId = detail?.gameId;
      if (!updatedGameId || updatedGameId !== gameIdRef.current || source === 'backend') return;
      setGraph(readStoredStoryGraph(updatedGameId) ?? EMPTY_STORY_GRAPH);
    };

    window.addEventListener(STORY_GRAPH_UPDATED_EVENT, onGraphUpdate);
    return () => window.removeEventListener(STORY_GRAPH_UPDATED_EVENT, onGraphUpdate);
  }, [source]);

  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <View
        className="mx-5 bg-canvas-subtle border border-border-default rounded-md flex-row items-center gap-2 p-2"
        style={shadow.paper}
      >
        <Pressable
          onPress={() => {
            if (router.canGoBack()) router.back();
            else router.replace('/');
          }}
          accessibilityRole="button"
          accessibilityLabel="돌아가기"
          className="h-8 w-8 items-center justify-center rounded-sm active:bg-canvas-inset"
        >
          <Text className="font-sans-semibold text-title text-fg-default">‹</Text>
        </Pressable>
        <View className="flex-1 min-w-0">
          <Text className="font-sans-semibold text-body text-fg-default">전체 지도</Text>
          <Text numberOfLines={1} className="font-sans text-caption text-fg-muted">
            {status === 'ready' ? graph.summary : '게임 세계 지도'}
          </Text>
        </View>
        {status === 'loading' ? <ActivityIndicator color={colors.accent.fg} /> : null}
      </View>

      <ScrollView
        className="flex-1"
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 20, gap: 10 }}
      >
        {message ? (
          <View className="rounded-sm border border-border-default bg-canvas-subtle px-3 py-2">
            <Text className="font-sans text-caption text-fg-muted">{message}</Text>
          </View>
        ) : null}

        {actionMessage ? (
          <View className="rounded-sm border border-border-default bg-canvas-subtle px-3 py-2">
            <Text className="font-sans text-caption text-fg-muted">{actionMessage}</Text>
          </View>
        ) : null}

        {status === 'loading' ? (
          <View className="items-center justify-center py-14">
            <Text className="font-sans text-body text-fg-muted">그래프를 불러오는 중입니다.</Text>
          </View>
        ) : null}

        {status === 'empty' ? (
          <View className="items-center justify-center py-14 gap-3">
            <Text className="font-sans-semibold text-body text-fg-default">진행 중인 게임이 없습니다.</Text>
            <Pressable
              onPress={() => router.replace('/')}
              accessibilityRole="button"
              accessibilityLabel="게임 화면으로 이동"
              className="rounded-sm border border-border-default bg-canvas-subtle px-3 py-2 active:bg-canvas-inset"
            >
              <Text className="font-sans text-body text-fg-default">게임 화면</Text>
            </Pressable>
          </View>
        ) : null}

        {status === 'error' ? (
          <View className="rounded-sm border border-danger-fg bg-canvas-subtle px-3 py-2">
            <Text className="font-sans text-caption text-danger-fg">
              {message ?? '그래프를 불러오지 못했습니다.'}
            </Text>
          </View>
        ) : null}

        {status === 'ready' ? (
          <StoryGraphPanel
            graph={graph}
            canvasHeight={430}
            framed
            sourceLabel={SOURCE_LABEL[source]}
            title="전체 지도"
            accessibilityLabel="전체 지도"
            selectedNodeId={selectedNodeId}
            onNodeSelect={setSelectedNodeId}
            onAction={runMapAction}
            actionDisabled={actionRunning}
          />
        ) : null}
      </ScrollView>
    </View>
  );
}
