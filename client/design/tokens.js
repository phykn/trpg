// Shared by Tailwind and components that need numeric values.
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
  danger: { fg: '#f19a8d' },
  success: { fg: '#9fcabd' },
  hp: { fg: '#f19a8d' },
  mp: { fg: '#9fcabd' },
  gold: { fg: '#e5bd76' },
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
  mono: ['GeistMono_400Regular'],
  'mono-medium': ['GeistMono_500Medium'],
};
const fontSize = {
  caption: ['12px', { lineHeight: '18px' }],
  panel: ['13px', { lineHeight: '20px' }],
  body: ['15px', { lineHeight: '24px' }],
  title: ['17px', { lineHeight: '26px' }],
  lead: ['18px', { lineHeight: '30px' }],
  scene: ['26px', { lineHeight: '36px' }],
  hero: ['36px', { lineHeight: '48px' }],
};
const layout = { mobile: 480, listRow: 124 };
module.exports = { colors, spacing, radius, fontFamily, fontSize, layout };
