const colors = {
  canvas: {
    default: '#0b1418',
    subtle: '#111f25',
    inset: '#0d191e',
    floating: '#17272d',
  },
  fg: {
    default: '#eee9dc',
    muted: '#b0bcbf',
    subtle: '#84989e',
    'on-emphasis': '#132024',
  },
  border: { default: '#2a3c43', strong: '#506369' },
  danger: { fg: '#f19a8d' },
  health: { fg: '#9fd69a' },
  gold: { fg: '#e5bd76', muted: '#302d24' },
  // Every meaning below owns its hue (ui.md 2.1): kinds, modifiers and health never borrow gold or danger.
  chip: { stat: '#aaacf2', help: '#bfd884', hinder: '#eb9ccd' },
  kind: { person: '#80c1e8', thing: '#86d0c4', obstacle: '#d2a9ec' },
  // Full boxes say whose side the fill is on: gold is the player's progress, red is trouble.
  box: { empty: '#2a3c43', full: '#e5bd76', danger: '#b8574b' },
  overlay: 'rgba(3,9,12,0.82)',
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
