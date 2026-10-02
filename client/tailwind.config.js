/** @type {import('tailwindcss').Config} */
const { colors, spacing, radius, fontFamily, fontSize, layout } = require('./design/tokens');

module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './screens/**/*.{ts,tsx}',
  ],
  presets: [require('nativewind/preset')],
  theme: {
    colors,
    spacing,
    borderRadius: radius,
    fontFamily,
    fontSize,
    extend: { maxWidth: { mobile: layout.mobile } },
  },
  plugins: [],
};
