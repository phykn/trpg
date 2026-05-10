import type { CombatBadge } from '@/logic/combat';
import type { Hero } from '@/logic/hero';
import type { LogEntry } from '@/logic/log';
import type { Quest } from '@/logic/quest';
import type { Place, StoryGraphModel } from '@/logic/story-graph';
import type { Subject } from '@/logic/subject';
import type {
  CombatEndPayload,
  CombatStartPayload,
  CombatTurnPayload,
  DonePayload,
  ErrorPayload,
  JudgePayload,
  NarrativeDeltaPayload,
  PendingCheckPayload,
  SuggestionsPayload,
} from './wire.gen';

export type PendingCheck = PendingCheckPayload;

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
  pendingCheck: PendingCheck | null;
  pendingConfirmation?: PendingConfirmation | null;
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

export type RuntimeMode = 'legacy' | 'graph';

export type SessionPayload = {
  game_id: string;
  state: FrontState;
  runtime?: RuntimeMode;
};

export type QuestAction = {
  kind: 'accept' | 'abandon';
  quest_id: string;
};

export type TurnRequest = {
  player_input: string;
  think: boolean;
  quest_action?: QuestAction;
};

export type RollRequest = {
  think: boolean;
};

export type ConfirmRequest = {
  confirmation_id: string;
  decision: 'confirm' | 'cancel';
  think: boolean;
};

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

export type GraphNamed = {
  name: string;
};

export type GraphInventoryItem = {
  name: string;
  qty: number;
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
  hp: GraphResource;
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
  hp: GraphResource;
  mp: GraphResource | null;
};

export type GraphCombatState = {
  round: number;
  outcome: 'ongoing' | 'victory' | 'defeat' | 'fled';
  participants: GraphCombatParticipant[];
};

export type GraphFrontState = {
  hero: GraphHeroState;
  quest: Quest | null;
  questOffers: Quest[];
  place: GraphPlaceState | null;
  combat: GraphCombatState | null;
  pendingConfirmation: PendingConfirmation | null;
  log: LogEntry[];
};

export type GraphSessionPayload = {
  game_id: string;
  state: GraphFrontState;
};

export type GraphActionResponse = {
  game_id: string;
  state: GraphFrontState;
  status?: string | null;
  message?: string | null;
};

export type GraphActionClientResponse = {
  game_id: string;
  state: FrontState;
  pendingConfirmation: PendingConfirmation | null;
  runtime: 'graph';
  status?: string | null;
  message?: string | null;
};

// `combat_*` and `judge` events are observability-only — the dispatch
// early-returns. UI state comes from `state` + `log_entry`.
export type StreamEvent =
  | { type: 'judge'; data: JudgePayload }
  | { type: 'pending_check'; data: PendingCheck }
  | { type: 'narrative_delta'; data: NarrativeDeltaPayload }
  | { type: 'suggestions'; data: SuggestionsPayload }
  | { type: 'log_entry'; data: LogEntry }
  | { type: 'state'; data: FrontState }
  | { type: 'combat_start'; data: CombatStartPayload }
  | { type: 'combat_turn'; data: CombatTurnPayload }
  | { type: 'combat_end'; data: CombatEndPayload }
  | { type: 'done'; data: DonePayload }
  | { type: 'error'; data: ErrorPayload };

export type StatKey = 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
export type GraphStatKey = 'body' | 'agility' | 'mind' | 'presence';
export type LevelUpStatKey = StatKey | GraphStatKey;

export type SkillCandidate = {
  id: string;
  name: string;
  description: string;
  type: 'attack' | 'heal' | 'buff' | 'debuff';
  target: 'self' | 'single' | 'area';
  primary_stat: StatKey;
  special_effect: string;
};

export type LevelUpPreviewResponse = {
  skill_candidates: SkillCandidate[];
};

export type LevelUpRequest = {
  stat_up: StatKey;
  skill_id: string | null;
  think: boolean;
};

export type GraphLevelUpRequest = {
  stat_up: GraphStatKey;
  skill_id: string | null;
  think: boolean;
};
