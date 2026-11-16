// The shapes of docs/engine/02-api.md.

export type Story = { story: string; title: string; intro: string };

export type Act = { id: string; label: string };

export type Line = {
  id: number; text: string; marks: string[]; struck: boolean; intro: string | null; about: number[]; new: boolean; acts: Act[];
};

export type Group = 'places' | 'people' | 'items' | 'seen' | 'heard';

export type Answer = 'hit' | 'miss' | 'blank';

export type GameView = {
  revision: number;
  story: { story: string; title: string };
  stage: 'start' | 'play' | 'closing' | 'over';
  start: {
    intro: string;
    stats: { key: string; name: string }[];
    acts: { id: string; plus2: string; plus1: string }[];
  } | null;
  place: {
    name: string;
    moves: { id: string; name: string; cells: number; unvisited: boolean }[];
    look: { id: string } | null;
    looked: boolean;
  };
  time: { text: string; left: number; last: boolean };
  people: { name: string; partner: boolean; act: string | null }[];
  offers: Act[];
  notebook: Record<Group, Line[]>;
  badge: number;
  conclude: { who: number[]; clues: number[] } | null;
  ending: {
    verdict: 'solved' | 'who_only' | 'wrong' | 'unsolved';
    answers: { who: Answer; how: Answer; why: Answer };
    turn: number;
    missed: { lies: string[]; held: string[]; locks: string[] };
  } | null;
};

export type TextKind = 'text' | 'ending' | 'omen' | 'event' | 'guide';

export type FeedItem =
  | { kind: 'move'; text: string }
  | { kind: 'roll'; text: string; won: boolean }
  | { kind: 'note'; text: string; lines: number[] }
  | { kind: TextKind; who: string | null; slot: number; topics?: string[] };

export type PastTurn = { kind: 'turn'; turn: number; said: string | null; feed: FeedItem[]; text: boolean };

export type TurnResult =
  | (PastTurn & { view: GameView })
  | { kind: 'refused'; code: string; turn: null; said: null; feed: []; text: false; view: GameView };

export type CommandBody =
  | { text: string }
  | { do: string; text?: string }
  | { read: number[] }
  | { conclude: { who: number | null; how: number | null; why: number | null } };

export type TextEvent =
  | { type: 'start' | 'end'; slot: number }
  | { type: 'delta' | 'replace'; slot: number; text: string }
  | { type: 'done' | 'error' };
