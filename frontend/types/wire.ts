import type { FrontState, PendingCheck } from './domain';
import type { LogEntry } from './ui';

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
  appearance: string;
};

export type InitRequest = {
  profile: string;
  player: PlayerInput;
};

export type SessionPayload = {
  game_id: string;
  state: FrontState;
};

export type TurnRequest = {
  player_input: string;
};

// `judge` and `combat_*` events are observed but their payloads are never
// destructured — `state` + `log_entry` are authoritative for the UI.
export type StreamEvent =
  | { type: 'judge'; data: unknown }
  | { type: 'pending_check'; data: PendingCheck }
  | { type: 'narrative_delta'; data: { text: string } }
  | { type: 'suggestions'; data: { items: string[] } }
  | { type: 'log_entry'; data: LogEntry }
  | { type: 'state'; data: FrontState }
  | { type: 'combat_start'; data: unknown }
  | { type: 'combat_turn'; data: unknown }
  | { type: 'combat_end'; data: unknown }
  | { type: 'done'; data: Record<string, never> }
  | { type: 'error'; data: { message: string; code: string } };
