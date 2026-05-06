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
