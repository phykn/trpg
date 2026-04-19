export type Tone = 'hp' | 'mp' | 'exp' | 'accent' | 'good' | 'bad' | 'neutral';

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
