import type { LogEntry } from '@/logic/log';
import type { Quest } from '@/logic/quest';
import type { PendingRoll } from '@/logic/roll';

import type { GraphSuggestion, SuggestionChip } from '../suggestions';
import type { PendingConfirmation, FrontState } from './clientState';

export type GraphResource = {
  current: number;
  maximum: number;
  state: string;
};

export type GraphHeart = {
  current: number;
  maximum: number;
};

export type GraphNamed = {
  id: string;
  name: string;
};

export type Chapter = {
  id: string;
  title: string;
  summary: string;
  status: 'locked' | 'active' | 'completed';
};

export type GraphEquipSlot = 'weapon' | 'armor' | 'accessory';

export type GraphInventoryItem = {
  id: string;
  name: string;
  qty: number;
  canUse: boolean;
  equipSlots: GraphEquipSlot[];
};

export type GraphEquipment = {
  weapon: GraphNamed | null;
  armor: GraphNamed | null;
  accessory: GraphNamed | null;
};

export type GraphHeroState = {
  id: string;
  name: string;
  level: number;
  exp: number;
  expMax: number;
  canLevelUp: boolean;
  gold: number;
  resources: {
    hp: GraphResource;
    mp: GraphResource;
  };
  stats: Record<string, number>;
  equipment: GraphEquipment;
  inventory: GraphInventoryItem[];
  status: string[];
  skills: string[];
};

export type GraphPlaceLink = {
  id: string;
  name: string;
  description: string;
};

export type GraphPlaceItem = {
  id: string;
  name: string;
  description: string;
};

export type GraphPlaceTarget = {
  id: string;
  name: string;
  kind: 'npc';
  alive: boolean;
  canAttack: boolean;
  level?: number;
  raceJob: string;
  gender: string;
  role: string;
};

export type GraphPlaceState = {
  id: string;
  name: string;
  description: string;
  exits: GraphPlaceLink[];
  items: GraphPlaceItem[];
  targets: GraphPlaceTarget[];
};

export type GraphCombatParticipant = {
  id: string;
  name: string;
  side: 'player' | 'enemy';
  hp: GraphResource | null;
  mp: GraphResource | null;
};

export type GraphCombatSupport = {
  id: string;
  kind: 'skill';
  name: string;
  action: 'attack' | 'defend' | 'flee' | 'talk';
  mpCost: number;
  usable: boolean;
};

export type GraphCombatState = {
  round: number;
  outcome: 'ongoing' | 'victory' | 'defeat' | 'escaped' | 'combat_stopped';
  playerHearts: GraphHeart;
  enemyHearts: GraphHeart;
  activeEnemyId: string;
  participants: GraphCombatParticipant[];
  availableSupports?: GraphCombatSupport[];
  escapeReady?: boolean;
  enemyPressure?: number;
  lastRoll?: number | null;
  lastDc?: number | null;
};

export type GraphDiscoveryEntry = {
  id: string;
  title: string;
  summary: string;
  stability: 'scene' | 'chapter' | 'campaign' | 'core';
  turnId?: number | null;
};

export type GraphDiscoveries = {
  memories: GraphDiscoveryEntry[];
  clues: GraphDiscoveryEntry[];
};

export type GraphFrontState = {
  hero: GraphHeroState;
  chapter: Chapter | null;
  scenarioCompleted: boolean;
  quest: Quest | null;
  questOffers: Quest[];
  place: GraphPlaceState | null;
  combat: GraphCombatState | null;
  discoveries?: GraphDiscoveries | null;
  pendingConfirmation: PendingConfirmation | null;
  pendingRoll: PendingRoll | null;
  log: LogEntry[];
};

export type GraphSessionPayload = {
  game_id: string;
  state: GraphFrontState;
  suggestions?: GraphSuggestion[];
};

export type GraphResultOutcome = 'success' | 'failure' | 'neutral';

export type GraphActionResponse = {
  game_id: string;
  state: GraphFrontState;
  status?: string | null;
  outcome?: GraphResultOutcome | null;
  message?: string | null;
  suggestions?: GraphSuggestion[];
};

export type GraphActionClientResponse = {
  game_id: string;
  state: FrontState;
  pendingConfirmation: PendingConfirmation | null;
  pendingRoll: PendingRoll | null;
  status?: string | null;
  outcome: GraphResultOutcome;
  message?: string | null;
  suggestions: SuggestionChip[];
};

export type GraphLevelUpGrowth =
  | { kind: 'max_hp' }
  | { kind: 'max_mp' }
  | { kind: 'stat'; stat: 'body' | 'agility' | 'mind' | 'presence' }
  | { kind: 'learn_skill'; skill_id: string }
  | { kind: 'learn_skill'; skill_id: string; skill: GraphLevelUpSkillSpec }
  | { kind: 'upgrade_skill'; skill_id: string };

export type GraphLevelUpSkillSpec = {
  id: string;
  name: string;
  description: string;
  action: 'attack' | 'defend' | 'flee' | 'talk';
  bonus: number;
  mp_cost: number;
};

export type GraphLevelUpChoice = {
  id: string;
  label: string;
  description: string;
  growth: GraphLevelUpGrowth;
};

export type GraphLevelUpChoicesResponse = {
  choices: GraphLevelUpChoice[];
};

export type GraphLevelUpRequest = {
  growth: GraphLevelUpGrowth;
};
