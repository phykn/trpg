export type Stats = { STR: number; DEX: number; CON: number; INT: number; WIS: number; CHA: number };
export type InventoryItem = { n: string; q: number; eq: boolean };
export type Memo = { t: string; m: string };

export type Hero = {
  name: string;
  race: string;
  class: string;
  level: number;
  exp: number; expMax: number;
  hp: number; hpMax: number;
  mp: number; mpMax: number;
  stats: Stats;
  inventory: InventoryItem[];
  memos: Memo[];
  status: string[];
  skills: string[];
  companions: string[];
};

export type SubjectKind = 'monster' | 'npc' | 'merchant';

export type Subject = {
  kind: SubjectKind;
  name: string;
  role: string;
  race: string;
  mood: string;
  trust: number;
  known: string[];
  level: number;
  hp: number;
  hpMax: number;
};

export type Quest = {
  title: string;
  giver: string;
  difficulty: { value: number; max: number; label: string };
  progress: { value: number; max: number };
  goals: string[];
  conditions: string[];
  rewards: string[];
};

export type Place = {
  name: string;
  date: string;
  hour: number;
  weather: string[];
  features: string[];
  surroundings: string[];
};

export type LogEntry =
  | { id: number; kind: 'gm'; text: string }
  | { id: number; kind: 'player'; text: string }
  | { id: number; kind: 'act'; text: string }
  | { id: number; kind: 'roll'; check: string; dc: number; roll: number; mod: number; result: 'success' | 'fail' };

export type BarDef = {
  label: string; value: number; max: number; color: string; display: string;
};

export type PanelSection = {
  label: string;
  text?: string;
  nodes?: [string, string | number][];
};

export type Panel = {
  title: string;
  meta?: string;
  bar?: BarDef;
  barSplit?: BarDef[];
  sections?: PanelSection[];
};

export type PanelSlot = {
  id: string;
  chip: { short: string; label: string; dot: string };
  panel: Panel | null;
};
