import type { CombatBadge } from '@/features/combat';
import type { StoryGraphModel } from '@/features/story-graph';
import type { LogEntry, Tone } from './ui';
import type { PendingCheck } from './wire';

export type RiskBadge = { label: string; tone: Tone };

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
  alive: boolean;
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
  reviveCoins: number;
  reviveCoinsMax: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  status: string[];
  skills: string[];
  companions: string[];
};

export type Subject = {
  name: string;
  alive: boolean;
  raceJob: string;
  gender: string;
  role: string;
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

export type DifficultyBadge = { label: string; tone: Tone | null };

export type Quest = {
  title: string;
  giver: string;
  difficulty: DifficultyBadge;
  goals: string[];
  conditions: string[];
  rewards: { gold: number; exp: number };
  summary: string;
};

export type PlaceSurrounding = {
  name: string;
  blurb: string;
  difficulty: string | null;
  risk: RiskBadge;
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
  risk: RiskBadge;
};

export type RollResult = 'success' | 'partial' | 'fail';

export type FrontState = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
  place: Place | null;
  combat: CombatBadge | null;
  log: LogEntry[];
  pendingCheck: PendingCheck | null;
  storyGraph: StoryGraphModel;
};
