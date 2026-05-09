import React from 'react';

import {
  EMPTY_STORY_GRAPH,
  mergeAndStoreStoryGraph,
  type StoryGraphModel,
} from '@/logic/story-graph';
import {
  clearAllForGame,
  clearStoredGameId,
  confirmGraphAction,
  getGraphSessionById,
  getSessionById,
  getLevelUpPreview,
  initGraphSession,
  loadLastSeenLocation,
  loadLastSeenQuestTitle,
  loadLastSeenSubjectId,
  loadStoredGameId,
  loadSuggestions,
  storeGameId,
  storeLastSeenLocation,
  storeLastSeenQuestTitle,
  storeLastSeenSubjectId,
  storeSuggestions,
  streamLevelUp,
  streamRoll,
  streamTurn,
  sendGraphAction,
  sendGraphInput,
} from '@/services';
import type { CombatBadge } from '@/logic/combat';
import type { Hero } from '@/logic/hero';
import type { LogEntry } from '@/logic/log';
import type { Quest } from '@/logic/quest';
import type { Place } from '@/logic/story-graph';
import type { Subject } from '@/logic/subject';
import type {
  FrontState,
  GraphActionClientResponse,
  GraphAction,
  InitRequest,
  PendingCheck,
  PendingConfirmation,
  RuntimeMode,
  SkillCandidate,
  StatKey,
  StreamEvent,
} from '@/services/wire';

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
  const [runtimeMode, setRuntimeMode] = React.useState<RuntimeMode>('legacy');
  const [hero, setHero] = React.useState<Hero | null>(null);
  const [subject, setSubject] = React.useState<Subject | null>(null);
  const [quest, setQuest] = React.useState<Quest | null>(null);
  const [place, setPlace] = React.useState<Place | null>(null);
  const [log, setLog] = React.useState<LogEntry[]>([]);

  const [pending, setPending] = React.useState<PendingCheck | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = React.useState<PendingConfirmation | null>(null);
  const [combat, setCombat] = React.useState<CombatBadge | null>(null);
  const [storyGraph, setStoryGraph] = React.useState<StoryGraphModel>(EMPTY_STORY_GRAPH);
  const [streaming, setStreaming] = React.useState(false);
  const [streamingText, setStreamingText] = React.useState('');
  const [suggestions, setSuggestionsRaw] = React.useState<string[]>([]);
  const [lastSeenLocation, setLastSeenLocation] = React.useState<string | null>(null);
  const [lastSeenQuestTitle, setLastSeenQuestTitle] = React.useState<string | null>(null);
  const [lastSeenSubjectId, setLastSeenSubjectId] = React.useState<string | null>(null);
  const [levelUpOpen, setLevelUpOpen] = React.useState(false);
  const [levelUpCandidates, setLevelUpCandidates] = React.useState<SkillCandidate[] | null>(null);

  const setSuggestions = React.useCallback(
    (next: React.SetStateAction<string[]>) => {
      setSuggestionsRaw((prev) => {
        const value = typeof next === 'function' ? (next as (p: string[]) => string[])(prev) : next;
        const id = gameIdRef.current;
        if (id) storeSuggestions(id, value);
        return value;
      });
    },
    [],
  );

  const gameIdRef = React.useRef<string | null>(null);
  // The streaming gate has to be synchronous — using the React state alone leaves a
  // window where a second click in the same tick reads the stale (false) value and
  // launches a parallel stream against the same game_id.
  const streamingRef = React.useRef(false);

  const aborts = React.useRef<Set<AbortController>>(new Set());
  const previewAbortRef = React.useRef<AbortController | null>(null);
  React.useEffect(() => {
    const pendingAborts = aborts.current;
    return () => {
      pendingAborts.forEach((a) => a.abort());
      pendingAborts.clear();
    };
  }, []);

  React.useEffect(() => {
    if (pending || pendingConfirmation) {
      previewAbortRef.current?.abort();
      setLevelUpOpen(false);
      setLevelUpCandidates(null);
    }
  }, [pending, pendingConfirmation]);

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
    setPendingConfirmation(s.pendingConfirmation ?? null);
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
        setSuggestions,
        setErrorMessage,
      }),
    [applyState],
  );

  const runGraphRequest = React.useCallback(
    async (call: () => Promise<GraphActionClientResponse>) => {
      if (streamingRef.current) return;
      streamingRef.current = true;
      setStreaming(true);
      setErrorMessage(null);
      setSuggestions([]);
      setStreamingText('');
      try {
        const response = await call();
        applyState(response.state, response.game_id);
        if (response.message) {
          setLog((current) =>
            mergeEntry(current, {
              id: -Date.now(),
              kind: 'gm',
              text: response.message ?? '',
            }),
          );
        }
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
      } finally {
        streamingRef.current = false;
        setStreaming(false);
      }
    },
    [applyState, setSuggestions],
  );

  const runStream = React.useCallback(
    async (call: (signal: AbortSignal) => Promise<void>) => {
      if (streamingRef.current) return;
      streamingRef.current = true;
      const controller = new AbortController();
      aborts.current.add(controller);
      setStreaming(true);
      setErrorMessage(null);
      setSuggestions([]);
      let needsResync = false;
      try {
        await call(controller.signal);
      } catch (err) {
        needsResync = true;
        if (controller.signal.aborted) return;
        setErrorMessage(err instanceof Error ? err.message : String(err));
      } finally {
        aborts.current.delete(controller);
        streamingRef.current = false;
        setStreaming(false);
        setStreamingText('');
        // Stream may have ended before a final `state` event arrived (network drop, server error, user abort).
        // The server's persisted state is authoritative — re-pull it so `pending` and friends don't drift.
        const id = gameIdRef.current;
        if (needsResync && id) {
          try {
            const payload = await getSessionById(id);
            if (payload) applyState(payload.state, payload.game_id);
          } catch {
            // resync failed too; the user's existing errorMessage covers it.
          }
        }
      }
    },
    [applyState],
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
      let payload = await getSessionById(stored);
      if (!payload) {
        payload = await getGraphSessionById(stored);
      }
      if (!payload) {
        // Stored id no longer exists on the server; drop the stale pointer.
        clearStoredGameId();
        setStatus('no-game');
        return;
      }
      setRuntimeMode(payload.runtime ?? 'legacy');
      rememberGameId(payload.game_id);
      applyState(payload.state, payload.game_id);
      setSuggestionsRaw(loadSuggestions(payload.game_id));
      setLastSeenLocation(loadLastSeenLocation(payload.game_id));
      setLastSeenQuestTitle(loadLastSeenQuestTitle(payload.game_id));
      setLastSeenSubjectId(loadLastSeenSubjectId(payload.game_id));
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
        const payload = await initGraphSession(body);
        storeGameId(payload.game_id);
        setRuntimeMode(payload.runtime ?? 'graph');
        rememberGameId(payload.game_id);
        applyState(payload.state, payload.game_id);
        setLastSeenLocation(null);
        setLastSeenQuestTitle(null);
        setLastSeenSubjectId(null);
        setPending(null);
        setPendingConfirmation(payload.state.pendingConfirmation ?? null);
        setStreamingText('');
        setSuggestions([]);
        setStatus('ready');
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
      if (!trimmed || !gameId || pending || pendingConfirmation) return;
      if (runtimeMode === 'graph') {
        void runGraphRequest(() => sendGraphInput(gameId, trimmed));
        return;
      }
      void runStream((signal) =>
        streamTurn(gameId, { player_input: trimmed, think: false }, handleEvent, signal),
      );
    },
    [gameId, pending, pendingConfirmation, runtimeMode, handleEvent, runGraphRequest, runStream],
  );

  const onQuestAction = React.useCallback(
    (kind: 'accept' | 'abandon', quest_id: string) => {
      if (!gameId || pending || pendingConfirmation) return;
      if (runtimeMode === 'graph') {
        void runGraphRequest(() =>
          sendGraphAction(gameId, {
            verb: 'transfer',
            what: quest_id,
            how: kind,
          }),
        );
        return;
      }
      void runStream((signal) =>
        streamTurn(
          gameId,
          { player_input: '', think: false, quest_action: { kind, quest_id } },
          handleEvent,
          signal,
        ),
      );
    },
    [gameId, pending, pendingConfirmation, runtimeMode, handleEvent, runGraphRequest, runStream],
  );

  const onGraphAction = React.useCallback(
    (action: GraphAction, textFallback?: string) => {
      if (!gameId || pending || pendingConfirmation) return;
      if (runtimeMode === 'graph') {
        void runGraphRequest(() => sendGraphAction(gameId, action));
        return;
      }
      const trimmed = textFallback?.trim();
      if (!trimmed) return;
      void runStream((signal) =>
        streamTurn(gameId, { player_input: trimmed, think: false }, handleEvent, signal),
      );
    },
    [gameId, pending, pendingConfirmation, runtimeMode, handleEvent, runGraphRequest, runStream],
  );

  const onConfirmPending = React.useCallback(
    (decision: 'confirm' | 'cancel') => {
      if (!gameId || !pendingConfirmation) return;
      const confirmationId = pendingConfirmation.id;
      void runGraphRequest(() =>
        confirmGraphAction(gameId, {
          confirmation_id: confirmationId,
          decision,
          think: false,
        }),
      );
    },
    [gameId, pendingConfirmation, runGraphRequest],
  );

  const onRoll = React.useCallback(() => {
    if (!gameId || !pending) return;
    void runStream((signal) => streamRoll(gameId, { think: false }, handleEvent, signal));
  }, [gameId, pending, handleEvent, runStream]);

  const onStop = React.useCallback(() => {
    aborts.current.forEach((a) => a.abort());
  }, []);

  const openLevelUp = React.useCallback(async () => {
    const id = gameIdRef.current;
    if (!id || streamingRef.current || pending || pendingConfirmation) return;
    setLevelUpOpen(true);
    setLevelUpCandidates(null);
    previewAbortRef.current?.abort();
    const controller = new AbortController();
    previewAbortRef.current = controller;
    try {
      const preview = await getLevelUpPreview(id, controller.signal);
      if (controller.signal.aborted) return;
      setLevelUpCandidates(preview.skill_candidates);
    } catch {
      if (controller.signal.aborted) return;
      setLevelUpCandidates([]);
    } finally {
      if (previewAbortRef.current === controller) {
        previewAbortRef.current = null;
      }
    }
  }, [pending, pendingConfirmation]);

  const cancelLevelUp = React.useCallback(() => {
    previewAbortRef.current?.abort();
    setLevelUpOpen(false);
    setLevelUpCandidates(null);
  }, []);

  const commitLevelUp = React.useCallback(
    (stat_up: StatKey, skill_id: string | null) => {
      const id = gameIdRef.current;
      if (!id) return;
      previewAbortRef.current?.abort();
      setLevelUpOpen(false);
      setLevelUpCandidates(null);
      void runStream((signal) =>
        streamLevelUp(id, { stat_up, skill_id, think: false }, handleEvent, signal),
      );
    },
    [handleEvent, runStream],
  );

  const goToNewGame = React.useCallback(() => {
    aborts.current.forEach((a) => a.abort());
    previewAbortRef.current?.abort();
    const id = gameIdRef.current;
    if (id) clearAllForGame(id);
    clearStoredGameId();
    setRuntimeMode('legacy');
    rememberGameId(null);
    setLevelUpOpen(false);
    setLevelUpCandidates(null);
    setStatus('no-game');
  }, [rememberGameId]);

  const displayLog = React.useMemo<LogEntry[]>(() => {
    if (!streamingText) return log;
    return [...log, { id: STREAMING_GM_ID, kind: 'gm', text: streamingText }];
  }, [log, streamingText]);

  const awaitingNarration = streaming && !pending && !pendingConfirmation;

  // Guarded by !streaming because hp can transiently hit 0 before reviveCoins
  // decrements during a roll/turn stream — wait for the final `state` event.
  const gameOver = !!hero && !streaming && hero.hp === 0 && hero.reviveCoins === 0;

  // Place wire type has no `id` — use `name` as the cache key (location names are unique per scenario).
  const placeKey = place?.name ?? null;
  const hasUnseenLocation = placeKey !== null && placeKey !== lastSeenLocation;

  const markLocationSeen = React.useCallback(() => {
    const id = gameIdRef.current;
    if (!id || !placeKey) return;
    setLastSeenLocation(placeKey);
    storeLastSeenLocation(id, placeKey);
  }, [placeKey]);

  // Quest wire carries `id`, but `title` is the cache key — id can churn across server-side renumbering, while titles are stable per-scenario.
  const questTitle = quest?.title ?? null;
  const hasUnseenQuest = questTitle !== null && questTitle !== lastSeenQuestTitle;

  const markQuestSeen = React.useCallback(() => {
    const id = gameIdRef.current;
    if (!id || !questTitle) return;
    setLastSeenQuestTitle(questTitle);
    storeLastSeenQuestTitle(id, questTitle);
  }, [questTitle]);

  // Subject wire type has no `id` — use `name` as the cache key.
  const subjectName = subject?.name ?? null;
  const hasUnseenSubject = subjectName !== null && subjectName !== lastSeenSubjectId;

  const markSubjectSeen = React.useCallback(() => {
    const id = gameIdRef.current;
    if (!id || !subjectName) return;
    setLastSeenSubjectId(subjectName);
    storeLastSeenSubjectId(id, subjectName);
  }, [subjectName]);

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
    pendingConfirmation,
    streaming,
    awaitingNarration,
    gameOver,
    suggestions,
    hasUnseenLocation,
    markLocationSeen,
    hasUnseenQuest,
    markQuestSeen,
    hasUnseenSubject,
    markSubjectSeen,
    onSend,
    onQuestAction,
    onGraphAction,
    onConfirmPending,
    onRoll,
    onStop,
    levelUpOpen,
    levelUpCandidates,
    openLevelUp,
    cancelLevelUp,
    commitLevelUp,
    startNewGame,
    goToNewGame,
    refresh,
  };
}
