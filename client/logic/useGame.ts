import { useEffect, useRef, useState } from 'react';

import { ApiError, createGame, getGame, getStories, getTurns, sendCommand, streamText } from '@/services/api';
import { clearGameId, loadGameId, storeGameId } from '@/services/storage';
import type { CommandBody, FeedItem, GameView, Story, TurnResult } from '@/services/types';

// ready: commands open. sending, streaming: locked. stuck: only the same command again. text_error: only the text again.
export type Phase = 'loading' | 'title' | 'ready' | 'sending' | 'streaming' | 'stuck' | 'text_error';

export type Entry =
  | { key: string; kind: 'said'; text: string }
  | { key: string; kind: 'move'; text: string }
  | { key: string; kind: 'roll'; text: string; won: boolean }
  | { key: string; kind: 'note'; text: string; lines: number[] }
  | { key: string; kind: 'text' | 'ending' | 'omen' | 'event' | 'guide'; who: string | null; text: string };

type Pending =
  | { kind: 'create'; requestId: string; story: string }
  | { kind: 'command'; requestId: string; revision: number; body: CommandBody };

export function newRequestId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

export function toEntries(turn: number, said: string | null, feed: FeedItem[]): Entry[] {
  const entries: Entry[] = said ? [{ key: `${turn}-said`, kind: 'said', text: said }] : [];
  feed.forEach((item, i) => {
    if ('slot' in item) entries.push({ key: `${turn}:${item.slot}`, kind: item.kind, who: item.who, text: '' });
    else entries.push({ ...item, key: `${turn}-${i}` } as Entry);
  });
  return entries;
}

export function useGame() {
  const [phase, setPhase] = useState<Phase>('loading');
  const [stories, setStories] = useState<Story[]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  const [view, setView] = useState<GameView | null>(null);
  const [log, setLog] = useState<Entry[]>([]);
  const game = useRef<string | null>(null);
  const pending = useRef<Pending | null>(null);
  const unread = useRef<number[]>([]);

  useEffect(() => {
    setSaved(loadGameId());
    getStories().then(setStories, () => setStories([])).finally(() => setPhase('title'));
  }, []);

  function setText(turn: number, slot: number, change: (text: string) => string) {
    setLog((entries) => entries.map((e) => (e.key === `${turn}:${slot}` && 'who' in e ? { ...e, text: change(e.text) } : e)));
  }

  async function readTexts(turns: number[]) {
    unread.current = turns;
    setPhase('streaming');
    while (unread.current.length) {
      const turn = unread.current[0];
      let done = false;
      await streamText(game.current!, turn, (e) => {
        if (e.type === 'start') setText(turn, e.slot, () => '');
        else if (e.type === 'delta') setText(turn, e.slot, (t) => t + e.text);
        else if (e.type === 'replace') setText(turn, e.slot, () => e.text);
        else if (e.type === 'done') done = true;
      });
      if (!done) { setPhase('text_error'); return; }
      unread.current = unread.current.slice(1);
    }
    setPhase('ready');
  }

  async function resume() {
    const id = loadGameId();
    if (!id) return;
    setPhase('loading');
    try {
      const [next, turns] = await Promise.all([getGame(id), getTurns(id, 1)]);
      game.current = id;
      setLog(turns.flatMap((t) => toEntries(t.turn!, t.said, t.feed)));
      setView(next);
      await readTexts(turns.filter((t) => t.text).map((t) => t.turn!));
    } catch {
      setPhase('title');   // the saved pointer stays: the game may open next time
    }
  }

  async function create(p: Extract<Pending, { kind: 'create' }>) {
    pending.current = p;
    setPhase('sending');
    try {
      const r = await createGame(p.requestId, p.story);
      pending.current = null;
      game.current = r.game;
      storeGameId(r.game);
      setSaved(r.game);
      setLog([]);
      setView(r.view);
      setPhase('ready');
    } catch {
      setPhase('stuck');
    }
  }

  async function run(p: Extract<Pending, { kind: 'command' }>) {
    pending.current = p;
    setPhase('sending');
    let result: TurnResult;
    try {
      result = await sendCommand(game.current!, p.requestId, p.revision, p.body);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.view) {
        pending.current = null;
        setView(e.view);
        setPhase('ready');
      } else if (e instanceof ApiError && (e.status === 409 || e.status === 404)) {
        pending.current = null;
        setPhase('title');
      } else {
        setPhase('stuck');
      }
      return;
    }
    pending.current = null;
    setView(result.view);
    if (result.kind === 'refused') { setPhase('ready'); return; }
    setLog((entries) => [...entries, ...toEntries(result.turn!, result.said, result.feed)]);
    if (result.text) await readTexts([result.turn!]);
    else setPhase('ready');
  }

  function send(body: CommandBody) {
    if (phase !== 'ready' || !view || !game.current) return;
    void run({ kind: 'command', requestId: newRequestId(), revision: view.revision, body });
  }

  function start(story: string) {
    if (phase !== 'title') return;
    void create({ kind: 'create', requestId: newRequestId(), story });
  }

  function resend() {
    const p = pending.current;
    if (p?.kind === 'create') void create(p);
    else if (p) void run(p);
  }

  function retryText() {
    void readTexts(unread.current);
  }

  // After the ending: the finished game is not offered again.
  function leave() {
    clearGameId();
    setSaved(null);
    game.current = null;
    setView(null);
    setLog([]);
    setPhase('title');
  }

  // What the player just typed shows at once, before the server answers with the turn that holds it.
  const p = pending.current;
  const outgoing = phase === 'sending' && p?.kind === 'command' && 'text' in p.body && p.body.text ? p.body.text : null;

  return { phase, stories, saved, view, log, outgoing, start, resume, send, resend, retryText, leave };
}
