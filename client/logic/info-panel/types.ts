import type { BarDef, ConfirmInfo, PartsCell, Tone } from '@/components/ui';
import type { CombatCommand, GraphAction, QuestAction } from '@/services/wire';

export type MetaSegment = { text: string; tone?: Tone };

export type PanelAction =
  | { kind: 'text'; label: string; text: string; confirm?: ConfirmInfo }
  | { kind: 'graph_action'; label: string; graphAction: GraphAction; textFallback?: string; confirm?: ConfirmInfo }
  | { kind: 'combat_command'; label: string; combatCommand: CombatCommand; textFallback?: string; confirm?: ConfirmInfo }
  | { kind: 'quest_action'; label: string; questAction: QuestAction; confirm?: ConfirmInfo };

export type PanelActions = {
  label: string;
  items: PanelAction[];
};

export type PanelSection = {
  label: string;
  text?: string;
  nodes?: [string, string | number][];
  mono?: boolean;
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
  chip: { short: string };
  panel: Panel | null;
};

