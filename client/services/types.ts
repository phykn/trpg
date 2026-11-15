export type Story = { story: string; title: string; intro: string };

export type Act = { id: string; label: string };

export type Line = { id: number; text: string; marks: string[]; struck: boolean; new: boolean; acts: Act[] };

export type Group = 'places' | 'people' | 'items' | 'seen' | 'heard';

export type Stage = 'start' | 'play' | 'closing' | 'over';

export type Answer = 'hit' | 'miss' | 'blank';

export type GameView = {
  revision: number;
  story: { story: string; title: string };
  stage: Stage;
  start: {
    intro: string;
    stats: { key: string; name: string }[];
    acts: { id: string; plus2: string; plus1: string }[];
  } | null;
  place: { name: string; moves: { id: string; name: string; cells: number; unvisited: boolean }[] };
  time: { text: string; left: number; last: boolean };
  people: { name: string; partner: boolean; act: string | null }[];
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

export type FeedItem =
  | { kind: 'move'; text: string }
  | { kind: 'roll'; text: string; won: boolean }
  | { kind: 'note'; text: string; lines: number[] }
  | { kind: 'text'; who: string | null; slot: number }
  | { kind: 'ending' | 'omen' | 'event' | 'guide'; who: null; slot: number };

export type TurnResult = {
  kind: 'turn' | 'refused';
  turn: number | null;
  said: string | null;
  feed: FeedItem[];
  text: boolean;
  code?: string;
  view: GameView;
};

export type PastTurn = Omit<TurnResult, 'view' | 'kind' | 'code'> & { kind: 'turn' };

export type CommandBody =
  | { text: string }
  | { do: string; text?: string }
  | { read: number[] }
  | { conclude: { who: number | null; how: number | null; why: number | null } };

export type TextEvent =
  | { type: 'start' | 'end'; slot: number }
  | { type: 'delta' | 'replace'; slot: number; text: string }
  | { type: 'done' | 'error' };
