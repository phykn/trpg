// Design tokens consumed by tailwind.config.js (Node/CJS) and TS via tokens.d.ts. Naming follows GitHub Primer.
const colors = {
  canvas: {
    default: '#EEE6D6',
    subtle: '#FBF8F3',
    inset: '#E0D5C0',
  },
  fg: {
    default: '#2D2A26',
    muted: '#6B6359',
    subtle: '#9A9285',
    'on-emphasis': '#FBF8F3',
  },
  border: {
    default: '#D6CCBA',
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
  revival: { fg: '#7E6D9A' },
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

// Two-family system: NotoSerifKR for all Korean prose / labels / titles,
// GeistMono for ASCII numerics and stat keys only. `serif*` aliases stay
// for callsites that already lean on the narration name.
const fontFamily = {
  sans: ['NotoSerifKR_400Regular'],
  'sans-medium': ['NotoSerifKR_500Medium'],
  'sans-semibold': ['NotoSerifKR_600SemiBold'],
  'sans-bold': ['NotoSerifKR_700Bold'],
  serif: ['NotoSerifKR_400Regular'],
  'serif-medium': ['NotoSerifKR_500Medium'],
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
  lead:      ['17px', { lineHeight: '29px', letterSpacing: '-0.2px' }],
  narration: ['20px', { lineHeight: '34px', letterSpacing: '-0.3px' }],
};

const toneColor = {
  hp: colors.hp.fg,
  mp: colors.mp.fg,
  exp: colors.exp.fg,
  revival: colors.revival.fg,
  accent: colors.accent.fg,
  good: colors.success.fg,
  bad: colors.danger.fg,
  neutral: colors.fg.subtle,
};

const shadow = {
  floating: {
    shadowColor: colors.fg.default,
    shadowOpacity: 0.06,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  paper: {
    shadowColor: colors.fg.default,
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 1,
  },
};

module.exports = { colors, spacing, radius, fontFamily, fontSize, toneColor, shadow };
