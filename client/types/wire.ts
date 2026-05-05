import type { CombatBadge } from '@/features/combat';
import type { Hero } from '@/features/hero';
import type { LogEntry } from '@/features/log';
import type { Quest } from '@/features/quest';
import type { Place, StoryGraphModel } from '@/features/story-graph';
import type { Subject } from '@/features/subject';
import type { ErrorPayload } from './wire.gen';

export type PendingCheck = {
  kind: 'stat' | 'recruit';
  dc: number;
  stat: string;
  stat_label: string;
  stat_value: number;
  mod: number;
  required_roll: number;
  tier: { value: number; max: number; label: string };
  target: string;
  reason: string;
};

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

export type PlayerInput = {
  name: string;
  race_id: string;
  gender: 'male' | 'female';
};

export type InitRequest = {
  profile: string;
  player: PlayerInput;
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

// `combat_*` events are observed but their payloads are never destructured —
// `state` + `log_entry` are authoritative for the UI. `judge` is also
// observability-only today (handleStreamEvent early-returns), but the payload
// shape is typed as a discriminated union so future debug/observability
// consumers stay safe across server changes.
type VerbWire = { name: string; target_ids: string[]; modifiers: Record<string, unknown> };
export type JudgeData =
  | { judge_kind: 'pending_check_trigger'; tier: number; stat: string; targets: string[]; reason: string }
  | { judge_kind: 'refuse'; refuse: { category: string; message_hint: string } }
  | { judge_kind: 'verb'; verb: VerbWire }
  | { judge_kind: 'verbs'; actions: VerbWire[] };

export type StreamEvent =
  | { type: 'judge'; data: JudgeData }
  | { type: 'pending_check'; data: PendingCheck }
  | { type: 'narrative_delta'; data: { text: string } }
  | { type: 'suggestions'; data: { items: string[] } }
  | { type: 'log_entry'; data: LogEntry }
  | { type: 'state'; data: FrontState }
  | { type: 'combat_start'; data: unknown }
  | { type: 'combat_turn'; data: unknown }
  | { type: 'combat_end'; data: unknown }
  | { type: 'done'; data: Record<string, never> }
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
