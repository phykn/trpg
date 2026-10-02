import { useEffect, useRef, useState } from 'react';

import { ko } from '@/locale/ko';
import { ApiError, chooseOption, getCatalog, loadGame, startGame } from '@/services/api';
import { loadGameId, storeGameId } from '@/services/storage';
import type { GameCatalog, GameCommand, GameView } from '@/services/types';

function requestId(): string {
  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
}

export function useGame() {
  const [catalog, setCatalog] = useState<GameCatalog | null>(null);
  const [view, setView] = useState<GameView | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [needsSync, setNeedsSync] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const pending = useRef<{ gameId: string; command: GameCommand } | null>(null);

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
        if (id) {
          const saved = await loadGame(id);
          if (!cancelled) setView(saved);
        } else {
          setCreating(true);
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
  }, []);

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

  async function refresh() {
    await run(async () => {
      if (!catalog) setCatalog(await getCatalog());
      const id = view?.game_id ?? loadGameId();
      if (id) accept(await loadGame(id));
      else setCreating(true);
    }, ko.restoreFailed);
  }

  async function start(name: string, role: string) {
    await run(async () => {
      accept(await startGame(name, role));
    }, ko.startFailed);
  }

  async function sendPending() {
    const saved = pending.current;
    if (!saved) return;
    await run(async () => {
      setNeedsSync(true);
      try {
        accept(await chooseOption(saved.gameId, saved.command));
      } catch (cause) {
        if (cause instanceof ApiError && (cause.status === 409 || cause.status === 422)) {
          accept(await loadGame(saved.gameId));
        }
        throw cause;
      }
    }, ko.connectionLost);
  }

  async function choose(optionId: string) {
    if (!view || inFlight.current || needsSync) return;
    pending.current = {
      gameId: view.game_id,
      command: { option_id: optionId, revision: view.revision, request_id: requestId() },
    };
    await sendPending();
  }

  function openNew() {
    if (inFlight.current) return;
    setCreating(true);
    if (!pending.current) setError('');
  }

  return {
    catalog, view, busy, error, creating, needsSync,
    start, choose, refresh, openNew,
    retry: () => pending.current ? sendPending() : refresh(),
    resume: () => setCreating(false),
  };
}
