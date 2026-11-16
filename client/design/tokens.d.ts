export const colors: {
  canvas: { default: string; subtle: string; inset: string; floating: string };
  fg: { default: string; muted: string; subtle: string; 'on-emphasis': string };
  border: { default: string; strong: string };
  danger: { fg: string };
  health: { fg: string };
  gold: { fg: string; muted: string };
  speaker: Record<1 | 2 | 3 | 4 | 5 | 6, string>;
  overlay: string;
};
export const spacing: Record<string, number>;
export const radius: Record<string, number>;
export const fontFamily: Record<string, string[]>;
export const fontSize: Record<string, [string, { lineHeight: string }]>;
export const layout: { mobile: number };
export const motion: { enter: number };
