/**
 * Design tokens — single source of truth for colors, spacing, typography.
 * Consumed by tailwind.config.js (Node/CJS) and TS code via tokens.d.ts.
 *
 * Naming follows GitHub Primer:
 *   canvas.*  — background surfaces (page → cards → insets)
 *   fg.*      — foreground text/icon colors by emphasis
 *   border.*  — stroke colors
 *   accent.*  — brand accent (fg + muted bg)
 *   danger/success — semantic states
 *   hp/mp/exp — domain-specific game meters
 */

const colors = {
  canvas: {
    default: '#F5F1EB',
    subtle: '#FBF8F3',
    inset: '#ECE6DC',
  },
  fg: {
    default: '#2D2A26',
    muted: '#6B6359',
    subtle: '#9A9285',
    'on-emphasis': '#FBF8F3',
  },
  border: {
    default: '#E0D8CB',
  },
  accent: {
    fg: '#C96442',
    muted: 'rgba(201,100,66,0.10)',
  },
  danger: { fg: '#B5534A' },
  success: { fg: '#7B8C70' },
  hp: { fg: '#C96442' },
  mp: { fg: '#7B8C70' },
  exp: { fg: '#B8894A' },
};

const spacing = {
  0: 0,
  0.5: 2,
  1: 4,
  1.5: 6,
  2: 8,
  2.5: 10,
  3: 12,
  3.5: 14,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
  10: 40,
  14: 56,
};

const radius = {
  none: 0,
  sm: 8,
  md: 14,
  lg: 18,
  xl: 24,
  full: 9999,
};

const fontFamily = {
  sans: ['Inter_400Regular'],
  'sans-medium': ['Inter_500Medium'],
  'sans-semibold': ['Inter_600SemiBold'],
  'sans-bold': ['Inter_700Bold'],
  serif: ['SourceSerif4_400Regular'],
  'serif-medium': ['SourceSerif4_500Medium'],
  mono: ['GeistMono_400Regular'],
  'mono-medium': ['GeistMono_500Medium'],
  'mono-semibold': ['GeistMono_600SemiBold'],
};

const fontSize = {
  meta:    ['10px', { lineHeight: '12px', letterSpacing: '1.2px' }],
  caption: ['11px', { lineHeight: '14px', letterSpacing: '0.3px' }],
  panel:   ['12px', { lineHeight: '18px', letterSpacing: '0px' }],
  body:    ['13px', { lineHeight: '20px', letterSpacing: '0px' }],
  title:   ['15px', { lineHeight: '21px', letterSpacing: '-0.1px' }],
  lead:    ['17px', { lineHeight: '29px', letterSpacing: '-0.2px' }],
};

const toneColor = {
  hp: colors.hp.fg,
  mp: colors.mp.fg,
  exp: colors.exp.fg,
  accent: colors.accent.fg,
  good: colors.success.fg,
  bad: colors.danger.fg,
  neutral: colors.fg.subtle,
};

module.exports = { colors, spacing, radius, fontFamily, fontSize, toneColor };
