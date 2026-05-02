import type { RollResult } from './domain';

export type Tone = 'hp' | 'mp' | 'exp' | 'revival' | 'accent' | 'good' | 'bad' | 'neutral';

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
  clampLines?: number;
};

export type ConfirmInfo = {
  title: string;
  subtitle?: string;
  blurb?: string;
  trust?: number;
  risk?: { label: string; tone: Tone };
  confirmLabel?: string;
};

export type MetaSegment = { text: string; tone?: Tone };

export type PanelAction = { label: string; intent: string; confirm?: ConfirmInfo };

export type PanelActions = {
  label: string;
  items: PanelAction[];
};

export type Panel = {
  empty?: boolean;
  title: string;
  meta?: MetaSegment[];
  bar?: BarDef;
  barSplit?: (BarDef | PartsCell)[];
  sections?: PanelSection[];
  actions?: PanelActions[];
};

export type PanelSlot = {
  id: string;
  chip: { short: string; dot?: boolean };
  panel: Panel | null;
};
