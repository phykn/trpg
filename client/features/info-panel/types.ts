import type { BarDef, ConfirmInfo, PartsCell, Tone } from '@/components/ui';

export type MetaSegment = { text: string; tone?: Tone };

export type PanelAction = { label: string; intent: string; confirm?: ConfirmInfo };

export type PanelActions = {
  label: string;
  items: PanelAction[];
};

export type PanelSection = {
  label: string;
  text?: string;
  nodes?: [string, string | number][];
  clampLines?: number;
};

export type PanelTitleAction = { label: string; onPress: () => void };

export type Panel = {
  empty?: boolean;
  title: string;
  meta?: MetaSegment[];
  titleAction?: PanelTitleAction;
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

export type { ConfirmInfo };
