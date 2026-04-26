// 백엔드 wire 형태. domain.ts (UI 표시용) 와 별개로 통신 계층이 받는 그대로.

import type { FrontState } from './domain';

// --- 새 게임 화면 -----------------------------------------------------------

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

// --- 턴 요청 ---------------------------------------------------------------

export type TurnRequest = {
  player_input: string;
};

// --- judge 결과 (SSE judge 이벤트의 data) ----------------------------------

export type JudgeAction =
  | { action: 'pass' }
  | { action: 'reject' }
  | { action: 'clarify'; question: string }
  | { action: 'combat'; targets: string[] }
  | { action: 'roll'; tier: string; stat: string; targets: string[] };

// --- pending_check (SSE pending_check 이벤트의 data) -----------------------

export type PendingCheck = {
  dc: number;
  stat: string;
  mod: number;
  required_roll: number;
  tier: { value: number; max: number; label: string };
  target: string;
};

// --- log entry (SSE log_entry 이벤트의 data, GET state.log 의 원소) -------

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

// --- SSE 이벤트 union ------------------------------------------------------

export type StreamEvent =
  | { type: 'judge'; data: JudgeAction }
  | { type: 'pending_check'; data: PendingCheck }
  | { type: 'narrative_delta'; data: { text: string } }
  | { type: 'log_entry'; data: WireLogEntry }
  | { type: 'state'; data: FrontState }
  | { type: 'done'; data: Record<string, never> }
  | { type: 'error'; data: { message: string; code: string } };
