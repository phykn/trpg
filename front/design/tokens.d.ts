export declare const colors: {
  canvas: { default: string; subtle: string; inset: string };
  fg: { default: string; muted: string; subtle: string; 'on-emphasis': string };
  border: { default: string };
  accent: { fg: string; muted: string };
  danger: { fg: string };
  success: { fg: string };
  hp: { fg: string };
  mp: { fg: string };
  exp: { fg: string };
};

export declare const spacing: Record<string, number>;

export declare const radius: {
  none: number;
  sm: number;
  md: number;
  lg: number;
  xl: number;
  full: number;
};

export declare const fontFamily: Record<string, string[]>;

export declare const fontSize: Record<
  string,
  readonly [string, { lineHeight: string; letterSpacing: string }]
>;

import type { Tone } from '@/types/ui';

export declare const toneColor: Record<Tone, string>;
