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

export type TurnRequest = {
  player_input: string;
  think: boolean;
};

export type RollRequest = {
  think: boolean;
};

// Story graph payload shipped by `GET /session/{id}/graph`. Fields mirror
// `server/src/api/schema.py:StoryGraphResponse`. The client's rich
// StoryGraphModel (in `presenters/storyGraph.ts`) is a superset built from
// the FrontState panels; this wire type is the server's narrower shape.
export type StoryGraphPayloadNode = {
  id: string;
  kind: string;
  label: string;
  detail: string;
};

export type StoryGraphPayloadEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

export type StoryGraphPayload = {
  nodes: StoryGraphPayloadNode[];
  edges: StoryGraphPayloadEdge[];
  summary: string;
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
