const colors = {
  canvas: {
    default: '#efede6',
    subtle: '#e5e2d8',
    inset: '#2b241d',
    floating: '#f8f7f2',
  },
  fg: {
    default: '#1f2328',
    muted: '#474d55',
    subtle: '#5c6269',
    'on-emphasis': '#fbfaf6',
  },
  border: { default: '#d3cfc4', strong: '#8f8a7e' },
  danger: { fg: '#b3261e' },
  health: { fg: '#256b2c' },
  gold: { fg: '#8a5300', muted: '#eadcbf' },
  // Every meaning below owns its hue (ui.md 2.1): kinds, modifiers and health never borrow gold or danger.
  chip: { stat: '#4a3fc0', help: '#4d6800', hinder: '#a8226f' },
  kind: { person: '#1a669c', thing: '#0b7166', obstacle: '#87309f' },
  // Full boxes say whose side the fill is on: gold is the player's progress, red is trouble.
  box: { empty: '#b9b4a6', full: '#8a5300', danger: '#b3261e' },
  overlay: 'rgba(31,35,40,0.5)',
};
const spacing = {
  0: 0, 0.5: 2, 1: 4, 1.5: 6, 2: 8, 2.5: 10, 3: 12,
  3.5: 14, 4: 16, 5: 20, 6: 24, 7: 28, 8: 32, 9: 36, 10: 40, 11: 44,
  12: 48, 14: 56, 16: 64, 20: 80, 24: 96, 80: 320, 96: 384,
};
const radius = { none: 0, sm: 4, md: 8, lg: 12, xl: 16, '2xl': 20, full: 9999 };
const fontFamily = {
  sans: ['NanumGothic_400Regular'],
  'sans-semibold': ['NanumGothic_700Bold'],
  serif: ['NanumMyeongjo_800ExtraBold'],
  'serif-body': ['NanumMyeongjo_400Regular'],
  'mono-medium': ['GeistMono_500Medium'],
};
const fontSize = {
  chip: ['12px', { lineHeight: '18px' }],
  caption: ['12px', { lineHeight: '18px' }],
  panel: ['13px', { lineHeight: '20px' }],
  body: ['15px', { lineHeight: '24px' }],
  title: ['17px', { lineHeight: '26px' }],
  hero: ['28px', { lineHeight: '36px' }],
  display: ['40px', { lineHeight: '48px' }],
};
const layout = { mobile: 412 };
// `reduced` replaces every beat under prefers-reduced-motion (ui.md 4.5).
const motion = {
  cloud: 600, die: 250, dieGap: 120, line: 200, chip: 180, settle: 2200, decisive: 150,
  box: 150, fold: 200, change: 150, blockedFade: 300, reduced: 100,
  typeRate: 60, shakeMax: 1500, stuck: 30000, enter: 220, ripple: 800,
  stamp: 220, jolt: 300, chapterIn: 400, chapterHold: 1800, chapterOut: 400,
};
module.exports = { colors, spacing, radius, fontFamily, fontSize, layout, motion };
