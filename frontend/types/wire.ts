import type { FrontState } from './domain';

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

export type JudgeAction =
  | { action: 'pass' }
  | { action: 'reject' }
  | { action: 'clarify'; question: string }
  | { action: 'combat'; targets: string[] }
  | { action: 'roll'; tier: string; stat: string; targets: string[] };

export type PendingCheck = {
  dc: number;
  stat: string;
  mod: number;
  required_roll: number;
  tier: { value: number; max: number; label: string };
  target: string;
};

export type WireLogEntry =
  | { id: number; kind: 'gm'; text: string }
  | { id: number; kind: 'player'; text: string }
  | { id: number; kind: 'act'; text: string }
  | {
      id: number;
      kind: 'roll';
      check: string;
      dc: number;
      roll: number;
      mod: number;
      result: 'success' | 'partial' | 'fail';
    };

export type CombatHand = 'main' | 'off';

export type CombatActionKind = 'attack' | 'flee' | 'pass' | 'death_save';

export type CombatStartData = {
  turn_order: string[];
  round: number;
  surprise: 'player' | 'enemy' | null;
  enemy_ids: string[];
};

export type CombatTurnData = {
  actor: string;
  action: CombatActionKind;
  grade: string;
  damage?: number;
  target?: string;
  hand?: CombatHand;
};

export type CombatEndData = {
  outcome: 'victory' | 'defeat' | 'fled';
};

export type StreamEvent =
  | { type: 'judge'; data: JudgeAction }
  | { type: 'pending_check'; data: PendingCheck }
  | { type: 'narrative_delta'; data: { text: string } }
  | { type: 'log_entry'; data: WireLogEntry }
  | { type: 'state'; data: FrontState }
  | { type: 'combat_start'; data: CombatStartData }
  | { type: 'combat_turn'; data: CombatTurnData }
  | { type: 'combat_end'; data: CombatEndData }
  | { type: 'done'; data: Record<string, never> }
  | { type: 'error'; data: { message: string; code: string } };
