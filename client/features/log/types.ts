export type RollResult = 'success' | 'partial' | 'fail';

export type LogEntry =
  | { id: number; kind: 'gm'; text: string }
  | { id: number; kind: 'player'; text: string }
  | { id: number; kind: 'act'; text: string }
  | {
      id: number;
      kind: 'roll';
      check: string;
      roll: number;
      margin: number;
      result: RollResult;
    };
