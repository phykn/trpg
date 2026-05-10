// Design tokens consumed by tailwind.config.js (Node/CJS) and TS via tokens.d.ts. Naming follows GitHub Primer.
const colors = {
  canvas: {
    default: '#14110f',
    subtle: '#25211d',
    inset: '#1b1714',
    floating: '#2b2621',
  },
  fg: {
    default: '#faf9f5',
    muted: '#a9a099',
    subtle: '#746d66',
    'on-emphasis': '#14110f',
  },
  border: {
    default: 'rgba(230,223,216,0.14)',
    strong: 'rgba(230,223,216,0.26)',
  },
  accent: {
    fg: '#cc785c',
    muted: 'rgba(204,120,92,0.16)',
  },
  danger: { fg: '#b5534a' },
  success: { fg: '#7b8c70' },
  hp: { fg: '#df876d' },
  mp: { fg: '#78b879' },
  exp: { fg: '#e8a55a' },
  revival: { fg: '#b39ac8' },
  gold: { fg: '#d4a85a' },
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
  sm: 4,
  md: 8,
  lg: 10,
  xl: 12,
  full: 9999,
};

// NanumGothic (Korean prose / labels / titles, weights 400/700) + GeistMono (ASCII numerics, stat values).
// medium/semibold both map to 700 — NanumGothic has no 500/600 weight.
const fontFamily = {
  sans: ['NanumGothic_400Regular'],
  'sans-medium': ['NanumGothic_700Bold'],
  'sans-semibold': ['NanumGothic_700Bold'],
  'sans-bold': ['NanumGothic_700Bold'],
  serif: ['NanumGothic_400Regular'],
  'serif-medium': ['NanumGothic_700Bold'],
  mono: ['GeistMono_400Regular'],
  'mono-medium': ['GeistMono_500Medium'],
  'mono-semibold': ['GeistMono_600SemiBold'],
};

const fontSize = {
  meta:      ['10px', { lineHeight: '12px', letterSpacing: '1.2px' }],
  caption:   ['11px', { lineHeight: '14px', letterSpacing: '0.3px' }],
  panel:     ['12px', { lineHeight: '18px', letterSpacing: '0px' }],
  body:      ['13px', { lineHeight: '20px', letterSpacing: '0px' }],
  title:     ['15px', { lineHeight: '21px', letterSpacing: '-0.1px' }],
  lead:      ['17px', { lineHeight: '28px', letterSpacing: '0px' }],
  narration: ['20px', { lineHeight: '34px', letterSpacing: '0px' }],
};

const toneColor = {
  hp: colors.hp.fg,
  mp: colors.mp.fg,
  exp: colors.exp.fg,
  revival: colors.revival.fg,
  gold: colors.gold.fg,
  accent: colors.accent.fg,
  good: colors.success.fg,
  bad: colors.danger.fg,
  neutral: colors.fg.subtle,
};

// Shadow API kept but rendered invisible — depth in the dark theme comes from borders + bg opacity, not light-and-shadow simulation.
const shadow = {
  floating: {
    shadowColor: '#000000',
    shadowOpacity: 0,
    shadowRadius: 0,
    shadowOffset: { width: 0, height: 0 },
    elevation: 0,
  },
  paper: {
    shadowColor: '#000000',
    shadowOpacity: 0,
    shadowRadius: 0,
    shadowOffset: { width: 0, height: 0 },
    elevation: 0,
  },
};

module.exports = { colors, spacing, radius, fontFamily, fontSize, toneColor, shadow };
