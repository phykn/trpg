import type { CombatBadge } from '@/logic/combat';
import type { Discoveries } from '@/logic/discoveries';
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
  chapter: Chapter | null;
  scenarioCompleted: boolean;
  quest: Quest | null;
  questOffers: Quest[];
  place: Place | null;
  combat: CombatBadge | null;
  discoveries: Discoveries;
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
};

export type GraphRollRequest = {
  roll_id: string;
};

type CombatSupportCommandFields = {
  support_id?: string;
  support_kind?: 'skill';
};

export type CombatCommand =
  | ({ command: 'attack'; target: string } & CombatSupportCommandFields)
  | ({ command: 'talk'; target: string } & CombatSupportCommandFields)
  | ({ command: 'defend' } & CombatSupportCommandFields)
  | ({ command: 'flee' } & CombatSupportCommandFields);

export type GraphAction = {
  verb:
    | 'move'
    | 'transfer'
    | 'use'
    | 'attack'
    | 'speak'
    | 'perceive'
    | 'decide'
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

export type StoryPatchLedgerStatus = 'accepted' | 'rejected' | 'skipped' | 'rolled_back';

export type StoryPatchLedgerIntent = 'none' | 'memory_candidate' | 'clue_candidate' | 'both';

export type StoryPatchLedgerEntryWire = {
  turn: number;
  status: StoryPatchLedgerStatus;
  intent_kind: StoryPatchLedgerIntent;
  reason: string;
  patches: Record<string, unknown>[];
  rejected_reasons: string[];
  changed_node_ids: string[];
  changed_edge_ids: string[];
};

export type StoryPatchLedgerEntry = {
  turn: number;
  status: StoryPatchLedgerStatus;
  intentKind: StoryPatchLedgerIntent;
  reason: string;
  patches: Record<string, unknown>[];
  rejectedReasons: string[];
  changedNodeIds: string[];
  changedEdgeIds: string[];
};

export type StoryPatchEntriesWireResponse = {
  game_id: string;
  entries: StoryPatchLedgerEntryWire[];
};

export type StoryPatchEntriesResponse = {
  game_id: string;
  entries: StoryPatchLedgerEntry[];
};

export type StoryDebtEntryWire = {
  id: string;
  title: string;
  turn?: number | null;
  reason: string;
};

export type StoryDebtEntry = {
  id: string;
  title: string;
  turn?: number | null;
  reason: string;
};

export type StoryDebtWire = {
  unresolved_clues: StoryDebtEntryWire[];
  orphan_characters: StoryDebtEntryWire[];
  orphan_items: StoryDebtEntryWire[];
  dangling_quest_beats: StoryDebtEntryWire[];
};

export type StoryDebt = {
  unresolvedClues: StoryDebtEntry[];
  orphanCharacters: StoryDebtEntry[];
  orphanItems: StoryDebtEntry[];
  danglingQuestBeats: StoryDebtEntry[];
};

export type StoryDebtWireResponse = {
  game_id: string;
  debt: StoryDebtWire;
};

export type StoryDebtResponse = {
  game_id: string;
  debt: StoryDebt;
};

export type StoryGraphNode = {
  id: string;
  type: string;
  properties?: Record<string, unknown>;
};

export type StoryGraphEdge = {
  id: string;
  type: string;
  from: string;
  to: string;
  properties?: Record<string, unknown>;
};

export type StoryGraph = {
  nodes: Record<string, StoryGraphNode>;
  edges: Record<string, StoryGraphEdge>;
};

export type StoryGraphResponse = {
  game_id: string;
  graph: StoryGraph;
};

export type StoryContract = {
  id: string;
  world: {
    title: string;
    locale: 'ko';
  };
  fixed: string[];
  forbid: string[];
  tone: {
    register: string;
    person: 'second';
  };
  budgets: {
    patches_per_turn: number;
    new_terms_per_turn: number;
  };
  allowed_ops: string[];
  stability_defaults: Record<string, string>;
};

export type StoryContractResponse = {
  game_id: string;
  contract: StoryContract;
};

export type StoryContractPreviewResponse = {
  game_id: string;
  ok: boolean;
  reasons: string[];
  contract?: StoryContract | null;
};

export type StoryRollbackWireResponse = {
  game_id: string;
  entry: StoryPatchLedgerEntryWire;
};

export type StoryRollbackResponse = {
  game_id: string;
  entry: StoryPatchLedgerEntry;
};

export type StoryPatchPreviewProposal = {
  reason: string;
  patches: Record<string, unknown>[];
  narration_brief?: string | null;
};

export type StoryPatchPreviewWireResponse = {
  game_id: string;
  ok: boolean;
  reasons: string[];
  changed_node_ids: string[];
  changed_edge_ids: string[];
};

export type StoryPatchPreviewResponse = {
  game_id: string;
  ok: boolean;
  reasons: string[];
  changedNodeIds: string[];
  changedEdgeIds: string[];
};

export type StoryPromptReplayRequest = {
  player_input: string;
  action: GraphAction;
};

export type StoryPromptReplayResponse = {
  game_id: string;
  agent: 'story_write';
  intent: Record<string, unknown>;
  system_prompt: string;
  user_payload: Record<string, unknown>;
};
