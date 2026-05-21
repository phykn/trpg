import React from 'react';

import {
  EMPTY_STORY_GRAPH,
  type StoryGraphModel,
} from '@/logic/story-graph';
import {
  clearAllForGame,
  clearStoredGameId,
  confirmGraphAction,
  getGraphSessionById,
  getGraphLevelUpOptions,
  initGraphSession,
  loadStoredGameId,
  loadSuggestions,
  storeGameId,
  storeSuggestions,
  requestGraphIntro,
  rollGraphPending,
  sendGraphAction,
  sendGraphCombatCommand,
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
  CombatCommand,
  Chapter,
  FrontState,
  GraphAction,
  GraphLevelUpChoice,
  GraphLevelUpGrowth,
  InitRequest,
  PendingConfirmation,
  SuggestionChip,
} from '@/services/wire';
import { useGraphActionRunner } from './requestRunner';

export type GameStatus = 'loading' | 'no-game' | 'ready' | 'error';

export type Game = ReturnType<typeof useGame>;

export function useGame() {
  const [status, setStatus] = React.useState<GameStatus>('loading');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const [gameId, setGameId] = React.useState<string | null>(null);
  const [hero, setHero] = React.useState<Hero | null>(null);
  const [subject, setSubject] = React.useState<Subject | null>(null);
  const [chapter, setChapter] = React.useState<Chapter | null>(null);
  const [scenarioCompleted, setScenarioCompleted] = React.useState(false);
  const [quest, setQuest] = React.useState<Quest | null>(null);
  const [questOffers, setQuestOffers] = React.useState<Quest[]>([]);
  const [place, setPlace] = React.useState<Place | null>(null);
  const [log, setLog] = React.useState<LogEntry[]>([]);

  const [pendingConfirmation, setPendingConfirmation] = React.useState<PendingConfirmation | null>(null);
  const [pendingRoll, setPendingRoll] = React.useState<PendingRoll | null>(null);
  const [combat, setCombat] = React.useState<CombatBadge | null>(null);
  const [storyGraph, setStoryGraph] = React.useState<StoryGraphModel>(EMPTY_STORY_GRAPH);
  const [suggestions, setSuggestionsRaw] = React.useState<SuggestionChip[]>([]);
  const [levelUpOpen, setLevelUpOpen] = React.useState(false);
  const [levelUpChoices, setLevelUpChoices] = React.useState<GraphLevelUpChoice[]>([]);
  const [levelUpLoading, setLevelUpLoading] = React.useState(false);
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

  const applyState = React.useCallback((s: FrontState) => {
    setHero(s.hero);
    setSubject(s.subject);
    setChapter(s.chapter);
    setScenarioCompleted(s.scenarioCompleted);
    setQuest(s.quest);
    setQuestOffers(s.questOffers ?? []);
    setPlace(s.place);
    setCombat(s.combat);
    setLog(s.log);
    setPendingConfirmation(s.pendingConfirmation ?? null);
    setPendingRoll(s.pendingRoll ?? null);
    setStoryGraph(s.storyGraph);
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
      applyState(payload.state);
      setSuggestionsRaw(payload.suggestions ?? loadSuggestions(payload.game_id));
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
        applyState(payload.state);
        setPendingConfirmation(payload.state.pendingConfirmation ?? null);
        setPendingRoll(payload.state.pendingRoll ?? null);
        setSuggestions(payload.suggestions ?? []);
        setStatus('ready');
        void runGraphActionRequest((signal, events) =>
          requestGraphIntro(payload.game_id, {
            signal,
            onNarrationDelta: events.onNarrationDelta,
            onResult: events.onResult,
          }),
        );
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
            onResult: events.onResult,
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
          onResult: events.onResult,
        }),
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
            onResult: events.onResult,
        }),
      );
    },
    [gameId, pendingConfirmation, pendingRoll, runGraphActionRequest],
  );

  const onCombatCommand = React.useCallback(
    (command: CombatCommand, label?: string) => {
      if (!gameId || pendingConfirmation || pendingRoll) return;
      void runGraphActionRequest(
        (signal, events) =>
          sendGraphCombatCommand(gameId, command, {
            signal,
            onNarrationDelta: events.onNarrationDelta,
            onResult: events.onResult,
          }),
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
        }, {
          signal,
          onNarrationDelta: events.onNarrationDelta,
          onResult: events.onResult,
        }),
      );
    },
    [gameId, pendingConfirmation, runGraphActionRequest],
  );

  const onRollPending = React.useCallback(
    (rollId: string) => {
      if (!gameId || !pendingRoll) return;
      void runGraphActionRequest((signal, events) =>
        rollGraphPending(gameId, {
          roll_id: rollId,
        }, {
          signal,
          onNarrationDelta: events.onNarrationDelta,
          onResult: events.onResult,
        }),
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
    setLevelUpLoading(true);
    setErrorMessage(null);
    try {
      const choices = await getGraphLevelUpOptions(id);
      if (gameIdRef.current === id) {
        setLevelUpChoices(choices);
      }
    } catch (err) {
      if (gameIdRef.current === id) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (gameIdRef.current === id) {
        setLevelUpLoading(false);
      }
    }
  }, [pendingConfirmation, pendingRoll]);

  const cancelLevelUp = React.useCallback(() => {
    setLevelUpOpen(false);
    setLevelUpChoices([]);
  }, []);

  const commitLevelUp = React.useCallback(
    (growth: GraphLevelUpGrowth) => {
      const id = gameIdRef.current;
      if (!id) return;
      setLevelUpOpen(false);
      setLevelUpChoices([]);
      void runGraphActionRequest((signal) =>
        sendGraphLevelUp(id, { growth }, { signal }),
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
    setLevelUpChoices([]);
    setStatus('no-game');
  }, [abortGraphActionRequest, rememberGameId]);

  const awaitingNarration = requestInFlight && !pendingConfirmation && !pendingRoll;

  const gameOver = !!hero && !requestInFlight && hero.hp === 0;

  return {
    status,
    errorMessage,
    gameId,
    hero,
    subject,
    chapter,
    scenarioCompleted,
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
    onSend,
    onQuestAction,
    onGraphAction,
    onCombatCommand,
    onConfirmPending,
    onRollPending,
    onStop,
    levelUpOpen,
    levelUpChoices,
    levelUpLoading,
    openLevelUp,
    cancelLevelUp,
    commitLevelUp,
    startNewGame,
    goToNewGame,
    refresh,
  };
}
