export type RollResult = 'success' | 'fail';
export type LogOutcome = 'success' | 'failure' | 'neutral';
export type NarrationCue = {
  kind: 'change' | 'constraint' | 'opportunity' | 'warning';
  label: string;
  text: string;
  scope?: 'delta' | 'temporary';
};

export type LogEntry =
  | { id: number; kind: 'gm'; text: string; outcome?: LogOutcome | null; cues?: NarrationCue[] }
  | { id: number; kind: 'player'; text: string }
  | { id: number; kind: 'act'; text: string }
  | {
      id: number;
      kind: 'roll';
      check: string;
      roll: number;
      margin: number;
      result: RollResult;
      bonus_breakdown?: { label: string; value: number }[];
    };
