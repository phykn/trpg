export type Named = { id: string; name: string; text: string };
export type Button = { id: string; label: string; enabled: boolean };
export type Meter = { id: string; name: string; value: number; boxes: number; fits: string[] };
export type Chip = { id: string; name: string; kind: 'edge' | 'snag'; target: string };
export type Card = { id: string; steps: string[]; odds: [number, number, number]; costs: string[] };

export type StoryCard = {
  id: string;
  title: string;
  synopsis: string;
  creation: { choose: boolean; approaches: { id: string; name: string; text?: string }[]; traits: Named[] };
};

export type GameView = {
  game_id: string;
  revision: number;
  turn: number;
  title: string;
  chapter: string;
  intro: string;
  place: Named;
  senses: string[];
  exits: Button[];
  people: { id: string; name: string; role: string; mood: string }[];
  obstacles: Meter[];
  danger: Meter;
  tags: Chip[];
  player: {
    approaches: Meter[];
    traits: Named[];
    wounds: number;
    gold: number;
    items: Named[];
    knowledge: Named[];
    skills: Named[];
  };
  quests: Named[];
  buttons: Button[];
  journal: { n: number; input: string; lines: string[]; narration: string | null }[];
  pending: { kind: 'confirm' | 'growth'; card: Card | null; options: Button[] } | null;
  ending: Named | null;
  narrated: boolean;
};

export type ActResult = {
  kind: 'turn' | 'confirm' | 'clarify' | 'rejected' | 'cancelled';
  view: GameView;
  turn: number | null;
  options: Button[];
  reason: string;
};

export type Command =
  | { text: string }
  | { action_id: string }
  | { confirm: string; accept: boolean };

export type Envelope = Command & { revision: number; request_id: string };

export type NarrationEvent =
  | { type: 'delta'; text: string }
  | { type: 'reset' }
  | { type: 'done'; text: string; tags: Record<string, string> }
  | { type: 'error'; retry: boolean };

export type Creation = { approaches: Record<string, number>; traits: string[] };
