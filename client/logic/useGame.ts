import { useEffect, useRef, useState } from 'react';

import { ko } from '@/locale/ko';
import { ApiError, act, getCatalog, loadGame, startGame, streamNarration } from '@/services/api';
import { loadGameId, storeGameId } from '@/services/storage';
import type { Button, Command, Creation, Envelope, GameView, NarrationEvent, StoryCard } from '@/services/types';

export type Narration = { turn: number; text: string; status: 'idle' | 'streaming' | 'done' | 'error'; canRetry: boolean };
export type Notice = { reason: string; options: Button[] } | null;

const IDLE: Narration = { turn: -1, text: '', status: 'idle', canRetry: false };

function requestId(): string {
  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
}

export function useGame() {
  const [catalog, setCatalog] = useState<StoryCard[] | null>(null);
  const [view, setView] = useState<GameView | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [needsSync, setNeedsSync] = useState(false);
  const [narration, setNarration] = useState<Narration>(IDLE);
  const [notice, setNotice] = useState<Notice>(null);
  const inFlight = useRef(false);
  const streaming = useRef(false);
  const mounted = useRef(true);
  const pending = useRef<{ gameId: string; envelope: Envelope } | null>(null);

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    async function restore() {
      inFlight.current = true;
      try {
        const book = await getCatalog();
        if (cancelled) return;
        setCatalog(book);
        const id = loadGameId();
        if (!id) setCreating(true);
        else {
          const saved = await loadGame(id);
          if (!cancelled) {
            accept(saved);
            if (!saved.narrated) void narrate(saved, saved.turn);
          }
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof ApiError ? cause.message : ko.restoreFailed);
      } finally {
        if (!cancelled) {
          inFlight.current = false;
          setBusy(false);
        }
      }
    }
    void restore();
    return () => {
      cancelled = true;
      mounted.current = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(work: () => Promise<void>, fallback: string) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    try {
      await work();
    } catch (cause) {
      if (mounted.current) setError(cause instanceof ApiError ? cause.message : fallback);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  function accept(next: GameView) {
    if (!mounted.current) return;
    pending.current = null;
    setNeedsSync(false);
    setView(next);
    setCreating(false);
    if (!storeGameId(next.game_id)) setError(ko.storageUnavailable);
  }

  async function narrate(target: GameView, turn: number) {
    if (streaming.current) return;
    streaming.current = true;
    let text = '';
    setNarration({ turn, text, status: 'streaming', canRetry: false });
    const onEvent = (event: NarrationEvent) => {
      if (!mounted.current) return;
      if (event.type === 'delta') text += event.text;
      else if (event.type === 'reset') text = '';
      if (event.type === 'done') {
        setNarration({ turn, text: event.text, status: 'done', canRetry: false });
        setView((old) => old && old.game_id === target.game_id ? {
          ...old,
          narrated: old.turn === turn,
          journal: old.journal.map((entry) => entry.n === turn ? { ...entry, narration: event.text } : entry),
          tags: old.tags.map((tag) => event.tags[tag.id] ? { ...tag, name: event.tags[tag.id] } : tag),
        } : old);
      } else if (event.type === 'error') {
        setNarration({ turn, text, status: 'error', canRetry: event.retry });
      } else {
        setNarration({ turn, text, status: 'streaming', canRetry: false });
      }
    };
    try {
      await streamNarration(target.game_id, turn, onEvent);
    } catch {
      if (mounted.current) setNarration({ turn, text, status: 'error', canRetry: true });
    } finally {
      streaming.current = false;
    }
  }

  async function refresh() {
    await run(async () => {
      if (!catalog) setCatalog(await getCatalog());
      const id = view?.game_id ?? loadGameId();
      if (id) accept(await loadGame(id));
      else setCreating(true);
    }, ko.restoreFailed);
  }

  async function start(story: string, creation?: Creation) {
    let started: GameView | null = null;
    await run(async () => {
      started = await startGame(story, creation);
      accept(started);
      setNotice(null);
    }, ko.startFailed);
    if (started) await narrate(started, 0);
  }

  async function sendPending() {
    const saved = pending.current;
    if (!saved) return;
    let turn: { view: GameView; n: number } | null = null;
    await run(async () => {
      setNeedsSync(true);
      try {
        const out = await act(saved.gameId, saved.envelope);
        accept(out.view);
        setNotice(out.kind === 'clarify' || out.kind === 'rejected'
          ? { reason: out.reason || ko.clarify, options: out.options } : null);
        if (out.kind === 'turn' && out.turn !== null) turn = { view: out.view, n: out.turn };
      } catch (cause) {
        if (cause instanceof ApiError && (cause.status === 409 || cause.status === 422)) {
          accept(await loadGame(saved.gameId));
        }
        throw cause;
      }
    }, ko.connectionLost);
    const next = turn as { view: GameView; n: number } | null;
    if (next) await narrate(next.view, next.n);
  }

  async function send(command: Command) {
    if (!view || inFlight.current || streaming.current || needsSync) return;
    pending.current = { gameId: view.game_id, envelope: { ...command, revision: view.revision, request_id: requestId() } };
    await sendPending();
  }

  function openNew() {
    if (inFlight.current) return;
    setCreating(true);
    if (!pending.current) setError('');
  }

  async function retry() {
    if (pending.current) return sendPending();
    if (view && narration.status === 'error' && narration.canRetry) return narrate(view, narration.turn);
    return refresh();
  }

  return {
    catalog, view, busy, error, creating, needsSync, narration, notice,
    start, send, refresh, openNew, retry,
    retryNarration: () => view && narration.canRetry ? narrate(view, narration.turn) : undefined,
    dismissNotice: () => setNotice(null),
    resume: () => setCreating(false),
  };
}
