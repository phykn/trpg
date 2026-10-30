export type Story = {
  id: string; title: string; premise: string; approaches: number[]; pick: number;
  approach_names: { id: string; name: string; hint: string }[];
  traits: { id: string; name: string; text: string }[];
};
export type Creation = { name: string; approaches: Record<string, number>; traits: string[] };

export type Chip = { kind: 'stat' | 'help' | 'guard' | 'hinder'; label: string; value: number };
export type Change = { kind: string; [key: string]: unknown };
export type StepRecord = {
  t: number; action: string; label: string; result: 'success' | 'fail' | 'none' | 'blocked';
  risk: 'low' | 'normal' | 'high'; dc: number | null; roll: { d1: number; d2: number } | null; mods: Chip[];
  total: number | null; decisive: number[]; changes: Change[];
};

export type Preview = {
  risk: 'low' | 'normal' | 'high'; mods: Chip[]; z: number; dc: number;
  stakes: { clock: number; weight: string | null };
  clock: { id: string; name: string; boxes: number; fill: number } | null;
  gain: { kind: 'fill'; boxes: number; fit: number; forced?: number } | { kind: 'tag'; remove: string | null }
    | { kind: 'topic' } | { kind: 'favor'; effects: string[] } | { kind: 'follow' };
};
export type Target = { id: string; name: string; fill?: number; boxes?: number } | null;
export type CardOption = {
  id: string; label: string; consumed?: boolean; note?: string | null; preview?: Preview; effects?: string[];
  with?: string; rely?: string | null; forced?: boolean; dc?: number; risk?: Preview['risk'];
};
export type Card = {
  id: string; kind: 'roll' | 'clarify' | 'confirm' | 'move';
  echo: { text: string; slots: { slot: string; label: string }[] };
  question?: string;
  plan: { step: { action: string; label: string; target: Target } | null; rest: string[] };
  options: CardOption[]; selected: string | null;
};

export type Box = { id: string; name: string; fill: number; boxes: number };
export type Tag = { owner?: string; slot: number; kind: 'edge' | 'snag'; life: string; name: string };
export type GameView = {
  revision: number;
  story: { id: string; title: string; premise: string };
  chapter: { k: number; title: string; aim: string };
  scene: {
    place: { id: string; name: string; senses: string[] };
    people: { id: string; name: string; attitude: string; with: boolean }[];
    things: { id: string; name: string }[];
    obstacles: (Box & { blocks: string[] })[];
    exits: { id: string; name: string; blocked: boolean }[];
    tags: Tag[];
  };
  player: {
    name: string;
    approaches: { id: string; name: string; value: number }[];
    traits: { id: string; name: string; spent: boolean }[];
    tags: Tag[]; things: { id: string; name: string; spent: boolean }[];
    wounds: number; wound_boxes: number; beats: number; beats_max: number; growth: number;
  };
  clocks: (Box & { kind: string })[];
  journal: {
    beliefs: { id: string; text: string; order: number; here: boolean; spent: boolean }[];
    owes: { debtor: string; creditor: string; kind: 'promise' | 'kindness'; name: string; promise: string }[];
    relations: { id: string; name: string; attitude: string }[];
    choices: { kind: 'cost' | 'fork'; name: string; chapter: number }[];
  };
  buttons: { action: string; label: string; rolls: boolean }[];
  growth: { action: string; label: string; kind: 'approach' | 'trait' | 'scar'; name: string; text?: string }[];
  card: Card | null;
  last: { turn: number; steps: StepRecord[]; narrated: boolean } | null;
  recaps: number[];
  ending: { id: string; title: string } | null;
  ledger?: { chapter: number; lines: { kind: 'give' | 'promise' | 'follow' | 'regards'; state?: string; text: string }[] }[];
};

export type CommandBody =
  | { text: string } | { action: string } | { card: string; pick: string } | { card: string; cancel: true };
export type CommandResult = {
  kind: 'turn' | 'card' | 'refused'; turn: number | null; steps: StepRecord[]; reason: string | null; view: GameView;
};
export type NarrationEvent =
  | { type: 'stage'; stage: 'writing' | 'checking' | 'rewriting'; attempt?: number }
  | { type: 'text'; text: string }
  | { type: 'done'; tags: { slot: number; owner: string; name: string }[] }
  | { type: 'error'; message?: string };
