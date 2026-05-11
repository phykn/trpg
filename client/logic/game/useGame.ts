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
  requestGraphIntro,
  rollGraphPending,
  sendGraphAction,
  sendGraphInput,
  sendGraphLevelUp,
} from '@/services';
import type { CombatBadge } from '@/logic/combat';
import type { Hero } from '@/logic/hero';
import type { LogEntry } from '@/logic/log';
import type { Quest } from '@/logic/quest';
import type { PendingRoll } from '@/logic/roll';
import type { Place } from '@/logic/story-graph';
import type { Subject } from '@/logic/subject';
import type {
  FrontState,
  GraphAction,
  InitRequest,
  PendingConfirmation,
  GraphStatKey,
  SuggestionChip,
} from '@/services/wire';
import { ko } from '@/locale/ko';
import { useGraphActionRunner, type OptimisticLogEntry } from './requestRunner';

export type GameStatus = 'loading' | 'no-game' | 'ready' | 'error';

export type Game = ReturnType<typeof useGame>;

const GRAPH_STAT_KEYS = new Set<GraphStatKey>(['body', 'agility', 'mind', 'presence']);

function optimisticAct(label?: string): OptimisticLogEntry[] {
  return label ? [{ kind: 'act', text: label }] : [];
}

export function useGame() {
  const [status, setStatus] = React.useState<GameStatus>('loading');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const [gameId, setGameId] = React.useState<string | null>(null);
  const [hero, setHero] = React.useState<Hero | null>(null);
  const [subject, setSubject] = React.useState<Subject | null>(null);
  const [quest, setQuest] = React.useState<Quest | null>(null);
  const [questOffers, setQuestOffers] = React.useState<Quest[]>([]);
  const [place, setPlace] = React.useState<Place | null>(null);
  const [log, setLog] = React.useState<LogEntry[]>([]);

  const [pendingConfirmation, setPendingConfirmation] = React.useState<PendingConfirmation | null>(null);
  const [pendingRoll, setPendingRoll] = React.useState<PendingRoll | null>(null);
  const [combat, setCombat] = React.useState<CombatBadge | null>(null);
  const [storyGraph, setStoryGraph] = React.useState<StoryGraphModel>(EMPTY_STORY_GRAPH);
  const [suggestions, setSuggestionsRaw] = React.useState<SuggestionChip[]>([]);
  const [lastSeenLocation, setLastSeenLocation] = React.useState<string | null>(null);
  const [lastSeenQuestTitle, setLastSeenQuestTitle] = React.useState<string | null>(null);
  const [lastSeenSubjectId, setLastSeenSubjectId] = React.useState<string | null>(null);
  const [levelUpOpen, setLevelUpOpen] = React.useState(false);
  const gameIdRef = React.useRef<string | null>(null);

  const setSuggestions = React.useCallback(
    (next: React.SetStateAction<SuggestionChip[]>) => {
      setSuggestionsRaw((prev) => {
        const value = typeof next === 'function' ? (next as (p: SuggestionChip[]) => SuggestionChip[])(prev) : next;
        const id = gameIdRef.current;
        if (id) storeSuggestions(id, value);
        return value;
      });
    },
    [],
  );

  const isActiveGameId = React.useCallback((id: string) => gameIdRef.current === id, []);

  React.useEffect(() => {
    if (pendingConfirmation || pendingRoll) {
      setLevelUpOpen(false);
    }
  }, [pendingConfirmation, pendingRoll]);

  const rememberGameId = React.useCallback((id: string | null) => {
    gameIdRef.current = id;
    setGameId(id);
  }, []);

  const applyState = React.useCallback((s: FrontState, stateGameId = gameIdRef.current) => {
    setHero(s.hero);
    setSubject(s.subject);
    setQuest(s.quest);
    setQuestOffers(s.questOffers ?? []);
    setPlace(s.place);
    setCombat(s.combat);
    setLog(s.log);
    setPendingConfirmation(s.pendingConfirmation ?? null);
    setPendingRoll(s.pendingRoll ?? null);
    if (stateGameId) {
      setStoryGraph(mergeAndStoreStoryGraph(stateGameId, s.storyGraph));
    } else {
      setStoryGraph(s.storyGraph);
    }
  }, []);

  const { requestInFlight, requestInFlightRef, runGraphActionRequest, abortGraphActionRequest } =
    useGraphActionRunner({
      applyState,
      setErrorMessage,
      setLog,
      setSuggestions,
      isActiveGameId,
    });

  const refresh = React.useCallback(async () => {
    setStatus('loading');
    setErrorMessage(null);
    try {
      const stored = loadStoredGameId();
      if (!stored) {
        setStatus('no-game');
        return;
      }
      const payload = await getGraphSessionById(stored);
      if (!payload) {
        // Stored id no longer exists on the server; drop the stale pointer.
        clearStoredGameId();
        setStatus('no-game');
        return;
      }
      rememberGameId(payload.game_id);
      applyState(payload.state, payload.game_id);
      setSuggestionsRaw(payload.suggestions ?? loadSuggestions(payload.game_id));
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
      setErrorMessage(null);
      try {
        const payload = await initGraphSession(body);
        storeGameId(payload.game_id);
        rememberGameId(payload.game_id);
        applyState(payload.state, payload.game_id);
        setLastSeenLocation(null);
        setLastSeenQuestTitle(null);
        setLastSeenSubjectId(null);
        setPendingConfirmation(payload.state.pendingConfirmation ?? null);
        setPendingRoll(payload.state.pendingRoll ?? null);
        setSuggestions(payload.suggestions ?? []);
        setStatus('ready');
        void runGraphActionRequest((signal) => requestGraphIntro(payload.game_id, { signal }));
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
        setStatus('error');
      }
    },
    [applyState, rememberGameId, runGraphActionRequest, setSuggestions],
  );

  const onSend = React.useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !gameId || pendingConfirmation || pendingRoll) return;
      void runGraphActionRequest(
        (signal, events) =>
          sendGraphInput(gameId, trimmed, {
            signal,
            onNarrationDelta: events.onNarrationDelta,
          }),
        [{ kind: 'player', text: trimmed }],
      );
    },
    [gameId, pendingConfirmation, pendingRoll, runGraphActionRequest],
  );

  const onQuestAction = React.useCallback(
    (kind: 'accept' | 'abandon', quest_id: string, label?: string) => {
      if (!gameId || pendingConfirmation || pendingRoll) return;
      void runGraphActionRequest((signal, events) =>
        sendGraphAction(gameId, {
          verb: 'transfer',
          what: quest_id,
          how: kind,
        }, {
          signal,
          onNarrationDelta: events.onNarrationDelta,
        }),
        optimisticAct(label),
      );
    },
    [gameId, pendingConfirmation, pendingRoll, runGraphActionRequest],
  );

  const onGraphAction = React.useCallback(
    (action: GraphAction, label?: string) => {
      if (!gameId || pendingConfirmation || pendingRoll) return;
      void runGraphActionRequest(
        (signal, events) =>
          sendGraphAction(gameId, action, {
            signal,
            onNarrationDelta: events.onNarrationDelta,
          }),
        optimisticAct(label),
      );
    },
    [gameId, pendingConfirmation, pendingRoll, runGraphActionRequest],
  );

  const onConfirmPending = React.useCallback(
    (decision: 'confirm' | 'cancel') => {
      if (!gameId || !pendingConfirmation) return;
      const confirmationId = pendingConfirmation.id;
      setPendingConfirmation(null);
      void runGraphActionRequest((signal, events) =>
        confirmGraphAction(gameId, {
          confirmation_id: confirmationId,
          decision,
          think: false,
        }, {
          signal,
          onNarrationDelta: events.onNarrationDelta,
        }),
      );
    },
    [gameId, pendingConfirmation, runGraphActionRequest],
  );

  const onRollPending = React.useCallback(
    (rollId: string) => {
      if (!gameId || !pendingRoll) return;
      void runGraphActionRequest((signal) =>
        rollGraphPending(gameId, {
          roll_id: rollId,
          think: false,
        }, { signal }),
      );
    },
    [gameId, pendingRoll, runGraphActionRequest],
  );

  const onStop = React.useCallback(() => {
    abortGraphActionRequest();
  }, [abortGraphActionRequest]);

  const openLevelUp = React.useCallback(async () => {
    const id = gameIdRef.current;
    if (!id || requestInFlightRef.current || pendingConfirmation || pendingRoll) return;
    setLevelUpOpen(true);
  }, [pendingConfirmation, pendingRoll]);

  const cancelLevelUp = React.useCallback(() => {
    setLevelUpOpen(false);
  }, []);

  const commitLevelUp = React.useCallback(
    (stat_up: GraphStatKey) => {
      const id = gameIdRef.current;
      if (!id) return;
      setLevelUpOpen(false);
      if (!isGraphStatKey(stat_up)) {
        setErrorMessage(ko.error.invalidStat);
        return;
      }
      void runGraphActionRequest((signal) =>
        sendGraphLevelUp(id, { stat_up, skill_id: null, think: false }, { signal }),
      );
    },
    [runGraphActionRequest],
  );

  const goToNewGame = React.useCallback(() => {
    abortGraphActionRequest();
    const id = gameIdRef.current;
    if (id) clearAllForGame(id);
    clearStoredGameId();
    rememberGameId(null);
    setLevelUpOpen(false);
    setStatus('no-game');
  }, [abortGraphActionRequest, rememberGameId]);

  const awaitingNarration = requestInFlight && !pendingConfirmation && !pendingRoll;

  // Guarded by !requestInFlight because hp can transiently hit 0 before reviveCoins
  // decrement during a graph action request; wait for the final state payload.
  const gameOver = !!hero && !requestInFlight && hero.hp === 0 && hero.reviveCoins === 0;

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
  const questTitle = quest?.title ?? questOffers[0]?.title ?? null;
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
    questOffers,
    place,
    combat,
    storyGraph,
    log,
    pendingConfirmation,
    pendingRoll,
    streaming: requestInFlight,
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
    onRollPending,
    onStop,
    levelUpOpen,
    openLevelUp,
    cancelLevelUp,
    commitLevelUp,
    startNewGame,
    goToNewGame,
    refresh,
  };
}

function isGraphStatKey(value: GraphStatKey): value is GraphStatKey {
  return GRAPH_STAT_KEYS.has(value);
}
