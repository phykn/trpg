/** @type {import('tailwindcss').Config} */
const { colors, spacing, radius, fontFamily, fontSize } = require('./design/tokens');

module.exports = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './screens/**/*.{ts,tsx}',
    './features/**/*.{ts,tsx}',
  ],
  presets: [require('nativewind/preset')],
  theme: {
    colors,
    spacing,
    borderRadius: radius,
    fontFamily,
    fontSize,
    extend: {},
  },
  plugins: [],
};
