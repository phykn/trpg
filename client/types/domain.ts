import type { LogEntry } from './ui';

export type Stat = {
  label: string;
  value: number;
};

export type Stats = Stat[];

export type InventoryItem = {
  name: string;
  qty: number;
};

export type EquipItem = {
  name: string;
};

export type Equipment = {
  weapon: EquipItem | null;
  armor: EquipItem | null;
  accessory: EquipItem | null;
};

export type Hero = {
  name: string;
  raceJob: string;
  gender: string;
  level: number;
  exp: number;
  expMax: number;
  canLevelUp: boolean;
  hp: number;
  hpMax: number;
  mp: number;
  mpMax: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  status: string[];
  skills: string[];
  companions: string[];
};

export type Subject = {
  name: string;
  raceJob: string;
  gender: string;
  trust: number;
  known: string[];
  level: number;
  hp: number;
  hpMax: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  skills: string[];
};

export type Quest = {
  title: string;
  giver: string;
  difficulty: string;
  goals: string[];
  conditions: string[];
  rewards: { gold: number; exp: number };
  summary: string;
};

export type PlaceSurrounding = {
  name: string;
  blurb: string;
  difficulty: string | null;
};

export type PlaceTarget = {
  name: string;
  level: number;
  raceJob: string;
  gender: string;
  blurb: string;
  trust: number;
};

export type Place = {
  name: string;
  description: string;
  dayPhase: string;
  weather: string[];
  features: string[];
  surroundings: PlaceSurrounding[];
  targets: PlaceTarget[];
};

export type RollResult = 'success' | 'partial' | 'fail';

export type CombatEnemy = {
  name: string;
  hp: number;
  hpMax: number;
  alive: boolean;
};

export type CombatBadge = {
  round: number;
  turnLabel: string;
  enemies: CombatEnemy[];
};

export type PendingCheck = {
  kind: 'stat' | 'death_save' | 'combat_roll';
  dc: number;
  stat: string;
  stat_label: string;
  stat_value: number | null;
  mod: number;
  required_roll: number;
  tier: { value: number; max: number; label: string };
  target: string;
  reason: string | null;
};

export type FrontState = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
  place: Place | null;
  combat: CombatBadge | null;
  log: LogEntry[];
  pendingCheck: PendingCheck | null;
};
