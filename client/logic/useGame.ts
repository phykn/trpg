import { useEffect, useRef, useState } from 'react';

import { ApiError, createGame, getGame, getStories, getTurns, sendCommand, streamText } from '@/services/api';
import { clearGameId, loadGameId, storeGameId } from '@/services/storage';
import type { CommandBody, FeedItem, GameView, RollResult, Story, TextKind } from '@/services/types';

// ready: commands open. sending, streaming: locked. stuck: only the same command again. text_error: only the text again.
export type Phase = 'loading' | 'title' | 'ready' | 'sending' | 'streaming' | 'stuck' | 'text_error';

// A line of the chat log; `key` only tells React the lines apart, `turn` and `slot` say where a line belongs.
export type Entry = { key: string; turn: number } & (
  | { kind: 'said'; text: string }
  | { kind: 'move'; text: string }
  | ({ kind: 'roll' } & RollResult)
  | { kind: 'note'; text: string; lines: number[] }
  | { kind: TextKind; slot: number; who: string | null; text: string; topics?: string[] }
);

type Pending =
  | { kind: 'create'; requestId: string; story: string }
  | { kind: 'command'; requestId: string; revision: number; body: CommandBody };

const makeRequestId = () => crypto.randomUUID();

function makeEntries(turn: number, said: string | null, feed: FeedItem[]): Entry[] {
  const lines = feed.map((item, i): Entry => {
    const key = `${turn}-${i}`;
    return 'slot' in item ? { ...item, key, turn, text: '' } : { ...item, key, turn };
  });
  return said ? [{ key: `${turn}-said`, turn, kind: 'said', text: said }, ...lines] : lines;
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

  function changeText(turn: number, slot: number, change: (text: string) => string) {
    setLog((entries) => entries.map((e) => (e.turn === turn && 'slot' in e && e.slot === slot ? { ...e, text: change(e.text) } : e)));
  }

  // Turn by turn, so a failure leaves the turns not yet read for retryText.
  async function readTexts(turns: number[]) {
    unread.current = turns;
    setPhase('streaming');
    while (unread.current.length) {
      const turn = unread.current[0];
      let done = false;
      await streamText(game.current!, turn, (e) => {
        if (e.type === 'start') changeText(turn, e.slot, () => '');
        else if (e.type === 'delta') changeText(turn, e.slot, (t) => t + e.text);
        else if (e.type === 'done') done = true;
      });
      if (!done) {
        setPhase('text_error');
        return;
      }
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
      setLog(turns.flatMap((t) => makeEntries(t.turn, t.said, t.feed)));
      setView(next);
      await readTexts(turns.filter((t) => t.text).map((t) => t.turn));
    } catch {
      setPhase('title');   // the pointer stays: the game may open next time
    }
  }

  async function create(p: Extract<Pending, { kind: 'create' }>) {
    pending.current = p;
    setPhase('sending');
    try {
      const reply = await createGame(p.requestId, p.story);
      pending.current = null;
      game.current = reply.game;
      storeGameId(reply.game);
      setSaved(reply.game);
      setLog([]);
      setView(reply.view);
      setPhase('ready');
    } catch {
      setPhase('stuck');
    }
  }

  async function run(p: Extract<Pending, { kind: 'command' }>) {
    pending.current = p;
    setPhase('sending');
    let result;
    try {
      result = await sendCommand(game.current!, p.requestId, p.revision, p.body);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.view) {   // the game moved on: show it as it is
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
    if (result.kind === 'refused') {
      setPhase('ready');
      return;
    }
    setLog((entries) => [...entries, ...makeEntries(result.turn, result.said, result.feed)]);
    if (result.text) await readTexts([result.turn]);
    else setPhase('ready');
  }

  function send(body: CommandBody) {
    if (phase !== 'ready' || !view || !game.current) return;
    void run({ kind: 'command', requestId: makeRequestId(), revision: view.revision, body });
  }

  function start(story: string) {
    if (phase !== 'title') return;
    void create({ kind: 'create', requestId: makeRequestId(), story });
  }

  function resend() {
    const p = pending.current;
    if (p?.kind === 'create') void create(p);
    else if (p) void run(p);
  }

  function retryText() {
    void readTexts(unread.current);
  }

  // A new game keeps the one in progress saved to pick up again; after the ending it is not offered again.
  function toTitle(keep: boolean) {
    if (!keep) clearGameId();
    setSaved(keep ? game.current : null);
    game.current = null;
    setView(null);
    setLog([]);
    setPhase('title');
  }

  // What the player just typed shows at once, as the turn it is about to become.
  const p = pending.current;
  const outgoing: Entry | null = phase === 'sending' && p?.kind === 'command' && 'text' in p.body && p.body.text
    ? { key: 'outgoing', turn: p.revision + 1, kind: 'said', text: p.body.text } : null;

  return {
    phase, stories, saved, view, log, outgoing, start, resume, send, resend, retryText,
    home: () => toTitle(true), leave: () => toTitle(false),
  };
}
