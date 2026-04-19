import type { RollResult } from './domain';

export type Tone = 'hp' | 'mp' | 'exp' | 'accent' | 'good' | 'bad' | 'neutral';

export type LogEntry =
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
      result: RollResult;
    };

export type BarDef = {
  label: string;
  value: number;
  max: number;
  tone: Tone;
  display: string;
  signed?: boolean;
};

export type DisplayPart = {
  label?: string;
  icon?: string;
  text: string;
  tone?: Tone;
};

export type PartsCell = {
  label: string;
  parts: DisplayPart[];
};

export type PanelSection = {
  label: string;
  text?: string;
  nodes?: [string, string | number][];
};

export type Panel = {
  title: string;
  meta?: string;
  bar?: BarDef;
  barSplit?: (BarDef | PartsCell)[];
  sections?: PanelSection[];
};

export type PanelSlot = {
  id: string;
  chip: { short: string; label: string };
  panel: Panel | null;
};
