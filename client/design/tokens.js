const colors = {
  transparent: 'transparent',
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
  accent: { fg: '#e5bd76', muted: '#302d24' },
  danger: { fg: '#f19a8d', muted: '#3a2422' },
  success: { fg: '#9fcabd', muted: '#1f3530' },
  gold: { fg: '#e5bd76' },
  chip: { stat: '#8fb3d9', help: '#9fcabd', hinder: '#f19a8d' },
  band: { fail: '#5a2f2b', mixed: '#5a4a2b', success: '#2b5a4a' },
  // What kind a scene entry is, told apart by hue alone (ui.md 2.1).
  kind: { person: '#8fb3d9', thing: '#9fcabd', obstacle: '#c9a8e8' },
  // Full boxes say whose side the fill is on: gold is the player's progress, red is trouble, grey is time spent.
  box: { empty: '#2a3c43', full: '#e5bd76', fit: '#9fcabd', next: '#f19a8d', danger: '#b8574b', time: '#84989e' },
  overlay: 'rgba(3,9,12,0.82)',
};
const spacing = {
  0: 0, 0.5: 2, 1: 4, 1.5: 6, 2: 8, 2.5: 10, 3: 12,
  3.5: 14, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 11: 44,
  12: 48, 14: 56, 16: 64, 20: 80, 24: 96, 80: 320, 96: 384,
};
const radius = { none: 0, sm: 4, md: 8, lg: 12, xl: 16, full: 9999 };
const fontFamily = {
  sans: ['NanumGothic_400Regular'],
  'sans-semibold': ['NanumGothic_700Bold'],
  serif: ['NanumMyeongjo_800ExtraBold'],
  mono: ['GeistMono_400Regular'],
  'mono-medium': ['GeistMono_500Medium'],
};
const fontSize = {
  chip: ['12px', { lineHeight: '18px' }],
  caption: ['12px', { lineHeight: '18px' }],
  panel: ['13px', { lineHeight: '20px' }],
  body: ['15px', { lineHeight: '24px' }],
  title: ['17px', { lineHeight: '26px' }],
  lead: ['18px', { lineHeight: '30px' }],
  hero: ['28px', { lineHeight: '36px' }],
  display: ['40px', { lineHeight: '48px' }],
};
const text = { narration: [18, 17, 16, 15, 14, 13], min: 13, chipMin: 12, lineHeight: 1.6 };
const layout = { mobile: 412 };
// `reduced` replaces every beat under prefers-reduced-motion (ui.md 4.5).
const motion = {
  cloud: 600, die: 250, dieGap: 120, line: 200, chip: 180, settle: 300, decisive: 150,
  box: 150, fold: 200, change: 150, blockedFade: 300, odds: 250, reduced: 100,
  typeRate: 60, shakeMax: 1500, stuck: 30000,
};
module.exports = { colors, spacing, radius, fontFamily, fontSize, text, layout, motion };
