import Svg, { Circle, Path } from 'react-native-svg';

// One stroke set on a 24 grid, so every icon has the same weight and optical size.
const SHAPES = {
  flag: [<Path key="a" d="M5 21V4" />, <Path key="b" d="M5 4h12l-2.5 4.5L17 13H5" />],
  eye: [<Path key="a" d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />, <Circle key="b" cx={12} cy={12} r={2.8} />],
  arrow: [<Path key="a" d="M5 12h13" />, <Path key="b" d="m13 6 6 6-6 6" />],
  send: [<Path key="a" d="M12 19V5.5" />, <Path key="b" d="m6 11 6-6 6 6" />],
  close: [<Path key="a" d="M6.5 6.5l11 11" />, <Path key="b" d="M17.5 6.5l-11 11" />],
  next: [<Path key="a" d="m9 5 7 7-7 7" />],
  retry: [<Path key="a" d="M4 12a8 8 0 1 0 2.4-5.7" />, <Path key="b" d="M4 4.5V9h4.5" />],
  book: [<Path key="a" d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5v-15z" />, <Path key="b" d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19" />],
} as const;

export type IconName = keyof typeof SHAPES;

export function Icon({ name, size, color, width = 1.8 }: { name: IconName; size: number; color: string; width?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width}
      strokeLinecap="round" strokeLinejoin="round" pointerEvents="none">
      {SHAPES[name]}
    </Svg>
  );
}
