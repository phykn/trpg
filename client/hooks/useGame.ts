import React from 'react';

import { mergeAndStoreStoryGraph } from '@/hooks/useStoryGraph';
import { EMPTY_STORY_GRAPH } from '@/presenters/storyGraph';
import {
  clearStoredGameId,
  getSessionById,
  initSession,
  loadStoredGameId,
  storeGameId,
  streamIntro,
  streamRoll,
  streamTurn,
} from '@/services';
import type {
  CombatBadge,
  FrontState,
  Hero,
  Place,
  Quest,
  Subject,
} from '@/types/domain';
import type { StoryGraphModel } from '@/types/storyGraph';
import type { LogEntry } from '@/types/ui';
import type { InitRequest, PendingCheck, StreamEvent } from '@/types/wire';

import { handleStreamEvent } from './handleStreamEvent';

export type GameStatus = 'loading' | 'no-game' | 'ready' | 'error';

export type Game = ReturnType<typeof useGame>;

const STREAMING_GM_ID = -1;

function mergeEntry(log: LogEntry[], entry: LogEntry): LogEntry[] {
  const idx = log.findIndex((e) => e.id === entry.id);
  if (idx === -1) return [...log, entry];
  const next = log.slice();
  next[idx] = entry;
  return next;
}

export function useGame() {
  const [status, setStatus] = React.useState<GameStatus>('loading');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const [gameId, setGameId] = React.useState<string | null>(null);
  const [hero, setHero] = React.useState<Hero | null>(null);
  const [subject, setSubject] = React.useState<Subject | null>(null);
  const [quest, setQuest] = React.useState<Quest | null>(null);
  const [place, setPlace] = React.useState<Place | null>(null);
  const [log, setLog] = React.useState<LogEntry[]>([]);

  const [pending, setPending] = React.useState<PendingCheck | null>(null);
  const [combat, setCombat] = React.useState<CombatBadge | null>(null);
  const [storyGraph, setStoryGraph] = React.useState<StoryGraphModel>(EMPTY_STORY_GRAPH);
  const [streaming, setStreaming] = React.useState(false);
  const [streamingText, setStreamingText] = React.useState('');
  const [suggestions, setSuggestions] = React.useState<string[]>([]);
  const [think, setThink] = React.useState(false);
  const gameIdRef = React.useRef<string | null>(null);

  const aborts = React.useRef<Set<AbortController>>(new Set());
  React.useEffect(() => {
    const pendingAborts = aborts.current;
    return () => {
      pendingAborts.forEach((a) => a.abort());
      pendingAborts.clear();
    };
  }, []);

  const rememberGameId = React.useCallback((id: string | null) => {
    gameIdRef.current = id;
    setGameId(id);
  }, []);

  const applyState = React.useCallback((s: FrontState, stateGameId = gameIdRef.current) => {
    setHero(s.hero);
    setSubject(s.subject);
    setQuest(s.quest);
    setPlace(s.place);
    setCombat(s.combat);
    setLog(s.log);
    setPending(s.pendingCheck);
    if (stateGameId) {
      setStoryGraph(mergeAndStoreStoryGraph(stateGameId, s.storyGraph));
    } else {
      setStoryGraph(s.storyGraph);
    }
  }, []);

  const handleEvent = React.useCallback(
    (ev: StreamEvent) =>
      handleStreamEvent(ev, {
        setPending,
        clearPending: () => setPending(null),
        appendStreamingText: (t) => setStreamingText((cur) => cur + t),
        clearStreamingText: () => setStreamingText(''),
        upsertLogEntry: (entry) => setLog((L) => mergeEntry(L, entry)),
        applyState,
        clearCombat: () => setCombat(null),
        setSuggestions,
        setErrorMessage,
      }),
    [applyState],
  );

  const runStream = React.useCallback(
    async (call: (signal: AbortSignal) => Promise<void>) => {
      if (streaming) return;
      const controller = new AbortController();
      aborts.current.add(controller);
      setStreaming(true);
      setErrorMessage(null);
      setSuggestions([]);
      try {
        await call(controller.signal);
      } catch (err) {
        if (controller.signal.aborted) return;
        setErrorMessage(err instanceof Error ? err.message : String(err));
      } finally {
        aborts.current.delete(controller);
        setStreaming(false);
        setStreamingText('');
      }
    },
    [streaming],
  );

  const refresh = React.useCallback(async () => {
    setStatus('loading');
    setErrorMessage(null);
    try {
      const stored = loadStoredGameId();
      if (!stored) {
        setStatus('no-game');
        return;
      }
      const payload = await getSessionById(stored);
      if (!payload) {
        // Stored id no longer exists on the server; drop the stale pointer.
        clearStoredGameId();
        setStatus('no-game');
        return;
      }
      rememberGameId(payload.game_id);
      applyState(payload.state, payload.game_id);
      setStatus('ready');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
      setStatus('error');
    }
  }, [applyState, rememberGameId]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const startNewGame = React.useCallback(
    async (body: InitRequest) => {
      setStatus('loading');
      setErrorMessage(null);
      try {
        const payload = await initSession(body);
        storeGameId(payload.game_id);
        rememberGameId(payload.game_id);
        applyState(payload.state, payload.game_id);
        setPending(null);
        setStreamingText('');
        setSuggestions([]);
        setStatus('ready');
        await runStream((signal) => streamIntro(payload.game_id, handleEvent, signal));
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
        setStatus('error');
      }
    },
    [applyState, handleEvent, rememberGameId, runStream],
  );

  const onSend = React.useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !gameId || pending) return;
      void runStream((signal) =>
        streamTurn(gameId, { player_input: trimmed, think }, handleEvent, signal),
      );
    },
    [gameId, pending, handleEvent, runStream, think],
  );

  const onRoll = React.useCallback(() => {
    if (!gameId || !pending) return;
    void runStream((signal) => streamRoll(gameId, { think }, handleEvent, signal));
  }, [gameId, pending, handleEvent, runStream, think]);

  const onStop = React.useCallback(() => {
    aborts.current.forEach((a) => a.abort());
  }, []);

  const goToNewGame = React.useCallback(() => {
    aborts.current.forEach((a) => a.abort());
    clearStoredGameId();
    rememberGameId(null);
    setStatus('no-game');
  }, [rememberGameId]);

  const displayLog = React.useMemo<LogEntry[]>(() => {
    if (!streamingText) return log;
    return [...log, { id: STREAMING_GM_ID, kind: 'gm', text: streamingText }];
  }, [log, streamingText]);

  const awaitingNarration = streaming && !pending;

  return {
    status,
    errorMessage,
    gameId,
    hero,
    subject,
    quest,
    place,
    combat,
    storyGraph,
    log: displayLog,
    pending,
    streaming,
    awaitingNarration,
    suggestions,
    think,
    setThink,
    onSend,
    onRoll,
    onStop,
    startNewGame,
    goToNewGame,
    refresh,
  };
}
