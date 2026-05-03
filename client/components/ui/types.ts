export type Tone =
  | 'hp' | 'mp' | 'exp' | 'revival' | 'gold'
  | 'accent' | 'good' | 'bad' | 'neutral';

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

export type ConfirmInfo = {
  title: string;
  subtitle?: string;
  blurb?: string;
  trust?: number;
  risk?: { label: string; tone: Tone };
  confirmLabel?: string;
};
