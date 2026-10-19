export const colors: {
  transparent: string;
  canvas: { default: string; subtle: string; inset: string; floating: string };
  fg: { default: string; muted: string; subtle: string; 'on-emphasis': string };
  border: { default: string; strong: string };
  danger: { fg: string; muted: string };
  health: { fg: string; muted: string };
  gold: { fg: string; muted: string };
  chip: { stat: string; help: string; hinder: string };
  kind: { person: string; thing: string; obstacle: string };
  box: { empty: string; full: string; danger: string };
  overlay: string;
};
export const spacing: Record<string, number>;
export const radius: Record<string, number>;
export const fontFamily: Record<string, string[]>;
export const fontSize: Record<string, [string, { lineHeight: string }]>;
export const layout: { mobile: number };
export const motion: {
  cloud: number; die: number; dieGap: number; line: number; chip: number; settle: number; decisive: number;
  box: number; fold: number; change: number; blockedFade: number; reduced: number;
  typeRate: number; shakeMax: number; stuck: number; enter: number; ripple: number;
};
