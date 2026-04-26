import React from 'react';

import {
  getCurrentSession,
  initSession,
  streamRoll,
  streamTurn,
} from '@/services';
import type { Hero, Place, Quest, Subject, FrontState } from '@/types/domain';
import type { LogEntry } from '@/types/ui';
import type {
  InitRequest,
  PendingCheck,
  StreamEvent,
} from '@/types/wire';

export type GameStatus = 'loading' | 'no-game' | 'ready' | 'error';

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
  const [streaming, setStreaming] = React.useState(false);
  const [streamingText, setStreamingText] = React.useState('');

  const aborts = React.useRef<Set<AbortController>>(new Set());
  React.useEffect(() => {
    const pendingAborts = aborts.current;
    return () => {
      pendingAborts.forEach((a) => a.abort());
      pendingAborts.clear();
    };
  }, []);

  const applyState = React.useCallback((s: FrontState) => {
    setHero(s.hero);
    setSubject(s.subject);
    setQuest(s.quest);
    setPlace(s.place);
    setLog(s.log);
  }, []);

  const refresh = React.useCallback(async () => {
    setStatus('loading');
    setErrorMessage(null);
    try {
      const payload = await getCurrentSession();
      if (!payload) {
        setStatus('no-game');
        return;
      }
      setGameId(payload.game_id);
      applyState(payload.state);
      setStatus('ready');
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
      setStatus('error');
    }
  }, [applyState]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const startNewGame = React.useCallback(
    async (body: InitRequest) => {
      setStatus('loading');
      setErrorMessage(null);
      try {
        const payload = await initSession(body);
        setGameId(payload.game_id);
        applyState(payload.state);
        setPending(null);
        setStreamingText('');
        setStatus('ready');
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
        setStatus('error');
      }
    },
    [applyState],
  );

  const handleEvent = React.useCallback(
    (ev: StreamEvent) => {
      switch (ev.type) {
        case 'judge':
          // 디버그용 — UI 영향 없음
          return;
        case 'pending_check':
          setPending(ev.data);
          return;
        case 'narrative_delta':
          setStreamingText((t) => t + ev.data.text);
          return;
        case 'log_entry':
          setLog((L) => mergeEntry(L, ev.data));
          return;
        case 'state':
          applyState(ev.data);
          setStreamingText('');
          return;
        case 'done':
          return;
        case 'error':
          setErrorMessage(ev.data.message);
          return;
      }
    },
    [applyState],
  );

  const runStream = React.useCallback(
    async (call: (signal: AbortSignal) => Promise<void>, opts: { clearPending: boolean }) => {
      if (!gameId || streaming) return;
      const controller = new AbortController();
      aborts.current.add(controller);
      setStreaming(true);
      setErrorMessage(null);
      try {
        await call(controller.signal);
      } catch (err) {
        if (controller.signal.aborted) return;
        setErrorMessage(err instanceof Error ? err.message : String(err));
      } finally {
        aborts.current.delete(controller);
        setStreaming(false);
        setStreamingText('');
        if (opts.clearPending) setPending(null);
      }
    },
    [gameId, streaming],
  );

  const onSend = React.useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !gameId || pending) return;
      void runStream(
        (signal) => streamTurn(gameId, { player_input: trimmed }, handleEvent, signal),
        { clearPending: false },
      );
    },
    [gameId, pending, handleEvent, runStream],
  );

  const onRoll = React.useCallback(() => {
    if (!gameId || !pending) return;
    void runStream(
      (signal) => streamRoll(gameId, handleEvent, signal),
      { clearPending: true },
    );
  }, [gameId, pending, handleEvent, runStream]);

  const onStop = React.useCallback(() => {
    aborts.current.forEach((a) => a.abort());
  }, []);

  const displayLog = React.useMemo<LogEntry[]>(() => {
    if (!streamingText) return log;
    return [...log, { id: STREAMING_GM_ID, kind: 'gm', text: streamingText }];
  }, [log, streamingText]);

  return {
    status,
    errorMessage,
    hero,
    subject,
    quest,
    place,
    log: displayLog,
    pending,
    streaming,
    onSend,
    onRoll,
    onStop,
    startNewGame,
    refresh,
  };
}
