import type { CombatBadge } from '@/logic/combat';
import type { Hero } from '@/logic/hero';
import type { LogEntry } from '@/logic/log';
import type { Quest } from '@/logic/quest';
import type { PendingRoll } from '@/logic/roll';
import type { Place, StoryGraphModel } from '@/logic/story-graph';
import type { Subject } from '@/logic/subject';
import type { GraphSuggestion, SuggestionChip } from './suggestions';

export type { GraphSuggestion, SuggestionChip } from './suggestions';

export type PendingConfirmation = {
  id: string;
  kind: string;
  title: string;
  body: string;
  confirmLabel: string;
  cancelLabel: string;
  targetLabel?: string | null;
};

export type FrontState = {
  hero: Hero;
  subject: Subject | null;
  quest: Quest | null;
  questOffers: Quest[];
  place: Place | null;
  combat: CombatBadge | null;
  log: LogEntry[];
  pendingConfirmation?: PendingConfirmation | null;
  pendingRoll?: PendingRoll | null;
  storyGraph: StoryGraphModel;
};

export type RaceCard = {
  id: string;
  name: string;
  description: string;
};

export type ProfileCard = {
  id: string;
  name: string;
  description: string;
  races: RaceCard[];
};

type PlayerInput = {
  name: string;
  race_id: string;
  gender: 'male' | 'female';
};

export type InitRequest = {
  profile: string;
  player: PlayerInput;
  locale: 'ko' | 'en';
};

export type SessionPayload = {
  game_id: string;
  state: FrontState;
  suggestions?: SuggestionChip[];
};

export type QuestAction = {
  kind: 'accept' | 'abandon';
  quest_id: string;
};

export type ConfirmRequest = {
  confirmation_id: string;
  decision: 'confirm' | 'cancel';
  think: boolean;
};

export type GraphRollRequest = {
  roll_id: string;
  think: boolean;
};

export type CombatCommand =
  | { command: 'attack'; target_id: string }
  | { command: 'skill'; target_id: string }
  | { command: 'defend' }
  | { command: 'flee' };

export type GraphAction = {
  verb:
    | 'move'
    | 'transfer'
    | 'use'
    | 'attack'
    | 'cast'
    | 'speak'
    | 'perceive'
    | 'query'
    | 'rest'
    | 'pass';
  what?: string | string[] | null;
  from?: string | null;
  to?: string | null;
  with?: string | null;
  how?: string | null;
  note?: string | null;
};

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

export type GraphPlaceTarget = {
  id: string;
  name: string;
  kind: 'npc' | 'enemy';
  alive: boolean;
  level: number;
  raceJob: string;
  gender: string;
  role: string;
  gold: number;
  stats: Record<string, number>;
  equipment: GraphEquipment;
  inventory: GraphInventoryItem[];
  skills: string[];
  status: string[];
};

export type GraphPlaceState = {
  id: string;
  name: string;
  description: string;
  exits: GraphPlaceLink[];
  targets: GraphPlaceTarget[];
};

export type GraphCombatParticipant = {
  id: string;
  name: string;
  side: 'player' | 'enemy';
  hp: GraphResource | null;
  mp: GraphResource | null;
};

export type GraphCombatState = {
  round: number;
  outcome: 'ongoing' | 'victory' | 'defeat' | 'fled';
  playerHearts: GraphHeart;
  enemyHearts: GraphHeart;
  activeEnemyId: string;
  participants: GraphCombatParticipant[];
  lastRoll?: number | null;
  lastDc?: number | null;
};

export type GraphFrontState = {
  hero: GraphHeroState;
  quest: Quest | null;
  questOffers: Quest[];
  place: GraphPlaceState | null;
  combat: GraphCombatState | null;
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
  | { kind: 'learn_skill'; skill_id: string }
  | { kind: 'learn_skill'; skill_id: string; skill: GraphLevelUpSkillSpec }
  | { kind: 'upgrade_skill'; skill_id: string };

export type GraphLevelUpSkillSpec = {
  id: string;
  name: string;
  description: string;
  kind: 'support';
  action: 'attack' | 'defend' | 'flee' | 'social';
  mp_cost: number;
  effect_template: 'dc_down' | 'extra_heart_damage' | 'prevent_heart_loss' | 'escape_boost';
  support_bonus: number;
  tags: string[];
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
  think: boolean;
};
