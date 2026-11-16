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
  // One per person met, in notebook order, so each speaker keeps a hue through the game.
  speaker: { 1: '#0f5f8c', 2: '#a1401a', 3: '#3d6b12', 4: '#6e3aa6', 5: '#0b6e63', 6: '#a0255a' },
  overlay: 'rgba(31,35,40,0.5)',
};
const spacing = {
  0: 0, 0.5: 2, 1: 4, 1.5: 6, 2: 8, 2.5: 10, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 9: 36, 10: 40, 11: 44, 12: 48, 20: 80,
  80: 320,
};
const radius = { sm: 4, xl: 16, '2xl': 20, full: 9999 };
const fontFamily = {
  sans: ['NanumGothic_400Regular'],
  'sans-semibold': ['NanumGothic_700Bold'],
  serif: ['NanumMyeongjo_800ExtraBold'],
  'serif-body': ['NanumMyeongjo_400Regular'],
  'mono-medium': ['GeistMono_500Medium'],
};
const fontSize = {
  chip: ['12px', { lineHeight: '18px' }],
  panel: ['13px', { lineHeight: '20px' }],
  body: ['15px', { lineHeight: '24px' }],
  input: ['16px', { lineHeight: '24px' }], // 16px keeps iOS from zooming in on focus
  title: ['17px', { lineHeight: '26px' }],
  hero: ['28px', { lineHeight: '36px' }],
  display: ['40px', { lineHeight: '48px' }],
};
const layout = { mobile: 412 };
const icon = { sm: 14, md: 16, lg: 18 };
module.exports = { colors, spacing, radius, fontFamily, fontSize, layout, icon };
