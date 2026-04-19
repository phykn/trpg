import type { TextStyle } from 'react-native';

const appFonts = {
  sansRegular: 'Inter_400Regular',
  sansMedium: 'Inter_500Medium',
  sansSemibold: 'Inter_600SemiBold',
  sansBold: 'Inter_700Bold',
  serifRegular: 'SourceSerif4_400Regular',
  serifMedium: 'SourceSerif4_500Medium',
  monoRegular: 'GeistMono_400Regular',
  monoMedium: 'GeistMono_500Medium',
  monoSemibold: 'GeistMono_600SemiBold',
} as const;

export type TypeKey = 'meta' | 'caption' | 'body' | 'title' | 'lead';

export const TYPE: Record<TypeKey, { size: number; lh: number; ls: number; weight: '400' | '500' | '600' | '700' }> = {
  meta:    { size: 10, lh: 12,   ls: 1.2,  weight: '600' },
  caption: { size: 11, lh: 14,   ls: 0.3,  weight: '500' },
  body:    { size: 13, lh: 20,   ls: 0,    weight: '400' },
  title:   { size: 15, lh: 21,   ls: -0.1, weight: '500' },
  lead:    { size: 17, lh: 29,   ls: -0.2, weight: '400' },
};

export const RADIUS = { sm: 10, md: 14, lg: 18, pill: 999 } as const;
export const SPACE  = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20 } as const;

export const Theme = {
  bg:        '#F5F1EB',
  bgElev:    '#ECE6DC',
  bgCard:    '#FBF8F3',
  border:    '#E0D8CB',
  text:      '#2D2A26',
  textDim:   '#6B6359',
  textFaint: '#9A9285',
  accent:    '#C96442',
  accentSoft:'rgba(201,100,66,0.10)',
  hp:        '#C96442',
  mp:        '#7B8C70',
  exp:       '#B8894A',
  good:      '#7B8C70',
  bad:       '#B5534A',
  fonts: appFonts,
  type:   TYPE,
  radius: RADIUS,
  space:  SPACE,
} as const;

export type ThemeType = typeof Theme;

export function typeStyle(key: TypeKey, extra: TextStyle = {}): TextStyle {
  const t = TYPE[key];
  return {
    fontSize: t.size,
    lineHeight: t.lh,
    letterSpacing: t.ls,
    fontWeight: t.weight,
    ...extra,
  };
}
