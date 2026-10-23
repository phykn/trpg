import { useEffect, useRef, useState } from 'react';

import { motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
import {
  ApiError, createGame, getGame, getStories, narrationPath, recapPath, sendCommand, stream,
} from '@/services/api';
import { clearGameId, loadGameId, storeGameId } from '@/services/storage';
import type {
  Card, CommandBody, CommandResult, Creation, GameView, NarrationEvent, StepRecord, Story,
} from '@/services/types';
import { type Beat, duration, timeline } from './reveal';

export type Phase =
  | 'loading' | 'start' | 'idle' | 'sending' | 'card' | 'rolling' | 'revealing' | 'narrating'
  | 'stuck' | 'narration_error' | 'blocked' | 'ending';

type Reveal = { steps: StepRecord[]; beats: Beat[]; start: number; card: Card | null; skipped: boolean };
export type Narration = { text: string | null; recap: string | null; error: string | null };
type Pending =
  | { kind: 'command'; requestId: string; revision: number; body: CommandBody; gameId: string }
  | { kind: 'create'; requestId: string; story: string; creation: Creation };

const EMPTY: Narration = { text: null, recap: null, error: null };

export function requestId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

export function destination(view: GameView, growthLater: boolean): Phase {
  if (view.ending) return 'ending';
  if (view.card) return 'card';
  if (view.growth.length && !growthLater) return 'card';
  return 'idle';
}

function recapChapter(steps: StepRecord[], view: GameView): number | null {
  for (const s of steps) {
    for (const c of s.changes) {
      if (c.kind === 'chapter') return c.from as number;
      if (c.kind === 'ending') return view.chapter.k;
    }
  }
  return null;
}

function renameTags(view: GameView, tags: { slot: number; owner: string; name: string }[]): GameView {
  if (!tags.length) return view;
  const named = (owner: string, slot: number) => tags.find((t) => t.owner === owner && t.slot === slot)?.name;
  return {
    ...view,
    player: { ...view.player, tags: view.player.tags.map((t) => ({ ...t, name: named('player', t.slot) ?? t.name })) },
    scene: { ...view.scene, tags: view.scene.tags.map((t) => ({ ...t, name: named(t.owner ?? '', t.slot) ?? t.name })) },
  };
}

export function useGame(reduced = false) {
  const [phase, setPhase] = useState<Phase>('loading');
  const [stories, setStories] = useState<Story[]>([]);
  const [view, setView] = useState<GameView | null>(null);
  const [before, setBefore] = useState<GameView | null>(null);   // rows keep these values until their beat
  const [notice, setNotice] = useState<string | null>(null);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [narration, setNarration] = useState<Narration>(EMPTY);
  const [growthLater, setGrowthLater] = useState(false);
  const [recaps, setRecaps] = useState<Record<number, string>>({});
  const recapsRef = useRef(recaps);
  recapsRef.current = recaps;
  const [sent, setSent] = useState<string | null>(null);

  const gameId = useRef<string | null>(null);
  const viewRef = useRef<GameView | null>(null);
  const pending = useRef<Pending | null>(null);
  const rollAt = useRef<number | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const turn = useRef<{ revealed: boolean; narrated: boolean; typed: boolean; recap: number | null; failed: boolean }>(
    { revealed: true, narrated: true, typed: true, recap: null, failed: false });
  const mounted = useRef(true);
  const growthRef = useRef(false);

  const later = (fn: () => void, ms: number) => { timers.current.push(setTimeout(fn, ms)); };

  function accept(next: GameView) {
    viewRef.current = next;
    setView(next);
  }

  function settle() {
    const v = viewRef.current;
    if (v) setPhase(destination(v, growthRef.current));
    if (v?.ending) void loadRecaps(v);
  }

  function maybeEnd() {
    const s = turn.current;
    if (!s.revealed) return;
    if (s.failed) { setPhase('narration_error'); return; }
    if (!s.narrated || !s.typed) { setPhase('narrating'); return; }
    settle();
  }

  async function read(path: string, onText: (text: string) => void, onDone: (e: NarrationEvent) => void) {
    let failed = false;
    await stream(path, (e) => {
      if (!mounted.current) return;
      if (e.type === 'text') onText(e.text);
      else if (e.type === 'done') onDone(e);
      else if (e.type === 'error') {
        failed = true;
        setNarration((n) => ({ ...n, error: e.message ?? '' }));
      }
    });
    return !failed;
  }

  async function narrate(n: number, recap: number | null) {
    const id = gameId.current;
    if (!id) return;
    turn.current = { ...turn.current, narrated: false, typed: false, recap, failed: false };
    setNarration(EMPTY);
    const ok = await read(narrationPath(id, n), (text) => setNarration((x) => ({ ...x, text })), (e) => {
      if (e.type === 'done' && viewRef.current) accept(renameTags(viewRef.current, e.tags));
    });
    if (ok && recap !== null) {
      const recapped = await read(recapPath(id, recap), (text) => {
        turn.current.typed = false;                   // the narration may be typed out already; the recap is not
        setNarration((x) => ({ ...x, recap: text }));
        setRecaps((r) => ({ ...r, [recap]: text }));    // the view lists only recaps cached before it was sent
      }, () => undefined);
      if (!recapped) { turn.current.failed = true; maybeEnd(); return; }
    }
    if (!mounted.current) return;
    if (!ok) { turn.current.failed = true; maybeEnd(); return; }
    turn.current.narrated = true;
    maybeEnd();
  }

  async function loadRecaps(v: GameView) {
    const id = gameId.current;
    if (!id) return;
    for (const k of v.recaps) {
      if (recapsRef.current[k]) continue;
      await read(recapPath(id, k), (text) => setRecaps((r) => ({ ...r, [k]: text })), () => undefined);
    }
  }

  function startReveal(steps: StepRecord[], n: number, next: GameView, card: Card | null) {
    const beats = timeline(steps, motion, reduced);
    setReveal({ steps, beats, start: Date.now(), card, skipped: false });
    turn.current = { revealed: false, narrated: false, typed: false, recap: null, failed: false };
    setNarration(EMPTY);
    setPhase('revealing');
    void narrate(n, recapChapter(steps, next));
    later(() => finishReveal(), duration(beats));
  }

  function finishReveal() {
    if (turn.current.revealed) return;
    turn.current.revealed = true;
    setBefore(null);
    setReveal((r) => (r ? { ...r, skipped: true } : r));
    maybeEnd();
  }

  function handle(p: Pending, result: CommandResult) {
    if (pending.current !== p) return;              // a late copy of an answer already used
    pending.current = null;
    setSent(null);
    const card = p.kind === 'command' && 'pick' in p.body ? viewRef.current?.card ?? null : null;
    const old = viewRef.current;
    if (result.kind === 'refused') setNotice(result.reason);
    if (!result.steps.length || result.turn === null) {
      accept(result.view);
      rollAt.current = null;
      settle();
      return;
    }
    const go = () => {
      setBefore(old);
      accept(result.view);
      startReveal(result.steps, result.turn as number, result.view, card?.kind === 'roll' ? card : null);
    };
    const wait = rollAt.current === null ? 0 : Math.max(0, rollAt.current + motion.cloud - Date.now());
    rollAt.current = null;
    if (wait) later(go, wait); else go();
  }

  function fail(p: Pending, cause: unknown) {
    if (pending.current !== p) return;
    if (cause instanceof ApiError) {
      pending.current = null;
      setSent(null);
      rollAt.current = null;
      if (p.kind === 'create') {
        setNotice(cause.reason ?? ko.serverError);
        setPhase('start');
      } else if (cause.status === 409 && cause.view) {
        accept(cause.view);
        setNotice(ko.conflict);
        settle();
      } else if (cause.status === 409) {
        setPhase('blocked');
      } else if (cause.status === 404) {
        clearGameId();
        gameId.current = null;
        viewRef.current = null;
        setView(null);
        setPhase('start');
      } else {
        setNotice(cause.reason ?? ko.serverError);
        settle();
      }
      return;
    }
    setPhase('stuck');                               // no answer: only the identical command may follow
  }

  function dispatch(p: Pending) {
    const attempt = p.kind === 'command'
      ? sendCommand(p.gameId, p.requestId, p.revision, p.body)
      : createGame(p.requestId, p.story, p.creation).then((out) => {
        gameId.current = out.game_id;
        storeGameId(out.game_id);
        return { kind: 'turn', turn: null, steps: [], reason: null, view: out.view } as CommandResult;
      });
    let answered = false;
    later(() => { if (!answered && pending.current === p) setPhase('stuck'); }, motion.stuck);
    attempt.then((r) => { answered = true; if (mounted.current) handle(p, r); },
      (e) => { answered = true; if (mounted.current) fail(p, e); });
  }

  function rolls(p: Pending | null): boolean {
    return p?.kind === 'command' && 'pick' in p.body && viewRef.current?.card?.kind === 'roll';
  }

  function send(p: Pending) {
    if (rolls(p)) {
      rollAt.current = Date.now();
      setPhase('rolling');
    } else setPhase('sending');
    dispatch(p);
  }

  function command(body: CommandBody) {
    const v = viewRef.current;
    const id = gameId.current;
    if (!v || !id || pending.current) return;
    if (!['idle', 'card'].includes(phase)) return;
    const p: Pending = { kind: 'command', requestId: requestId(), revision: v.revision, body, gameId: id };
    pending.current = p;
    setNotice(null);
    setSent('text' in body ? body.text : null);
    send(p);
  }

  function resend() {
    const p = pending.current;
    if (p && phase === 'stuck') send(p);             // the same request id and body: the receipt answers
  }

  function create(story: string, creation: Creation) {
    if (pending.current) return;
    const p: Pending = { kind: 'create', requestId: requestId(), story, creation };
    pending.current = p;
    setNotice(null);
    send(p);
  }

  async function restore() {
    try {
      setStories(await getStories());
      const id = loadGameId();
      if (!id) { setPhase('start'); return; }
      gameId.current = id;
      const saved = await getGame(id);
      if (!mounted.current) return;
      accept(saved);
      if (saved.last) {
        turn.current = { revealed: true, narrated: false, typed: true, recap: null, failed: false };
        setPhase('narrating');
        await narrate(saved.last.turn, recapChapter(saved.last.steps, saved));
      } else settle();
    } catch (cause) {
      if (!mounted.current) return;
      if (cause instanceof ApiError && cause.status === 404) {
        clearGameId();
        setPhase('start');
      } else setPhase('blocked');                    // the pointer stays: a failed restore never clears it
    }
  }

  useEffect(() => {
    mounted.current = true;
    void restore();
    return () => {
      mounted.current = false;
      timers.current.forEach(clearTimeout);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const newGame = () => { if (!pending.current) { setNotice(null); setPhase('start'); } };

  return {
    phase, stories, view, before, notice, reveal, narration, recaps, sent, growthLater, gameId: gameId.current,
    // A creation in flight or lost keeps the start screen; a lost roll keeps its card, where the resend goes.
    creating: pending.current?.kind === 'create',
    lostRoll: phase === 'stuck' && rolls(pending.current),
    recapDue: turn.current.recap !== null && !narration.recap,
    command, resend, create,
    skip: () => { if (phase === 'revealing') finishReveal(); },
    typed: () => { turn.current.typed = true; maybeEnd(); },
    retryNarration: () => {
      const last = viewRef.current?.last;
      if (phase !== 'narration_error' || !last) return;
      setPhase('narrating');
      void narrate(last.turn, turn.current.recap);
    },
    laterGrowth: () => { growthRef.current = true; setGrowthLater(true); settle(); },
    openGrowth: () => { growthRef.current = false; setGrowthLater(false); if (phase === 'idle') setPhase('card'); },
    newGame,
    toTitle: () => { if (['idle', 'card'].includes(phase)) newGame(); },
    canResume: phase === 'start' && !!view && !view.ending,
    resume: () => { const v = viewRef.current; if (phase === 'start' && v && !v.ending) setPhase(destination(v, growthRef.current)); },
  };
}

export type Game = ReturnType<typeof useGame>;
