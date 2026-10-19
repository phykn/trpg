import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { colors } from '@/design/tokens';

// One stroke set on a 24 grid, so every icon has the same weight and optical size.
const SHAPES = {
  flag: [<Path key="a" d="M5 21V4" />, <Path key="b" d="M5 4h12l-2.5 4.5L17 13H5" />],
  pin: [<Path key="a" d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" />, <Circle key="b" cx={12} cy={10} r={2.3} />],
  eye: [<Path key="a" d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />, <Circle key="b" cx={12} cy={12} r={2.8} />],
  alert: [<Path key="a" d="M12 3.5 2.5 20h19L12 3.5z" />, <Path key="b" d="M12 10v4.5" />, <Path key="c" d="M12 17.2v.1" />],
  arrow: [<Path key="a" d="M5 12h13" />, <Path key="b" d="m13 6 6 6-6 6" />],
  lock: [<Rect key="a" x={5} y={11} width={14} height={10} rx={2} />, <Path key="b" d="M8 11V8a4 4 0 0 1 8 0v3" />],
  user: [<Circle key="a" cx={12} cy={8} r={4} />, <Path key="b" d="M4.5 21c.6-4 3.7-6.5 7.5-6.5s6.9 2.5 7.5 6.5" />],
  menu: [<Path key="a" d="M4 7h16" />, <Path key="b" d="M4 12h16" />, <Path key="c" d="M4 17h16" />],
  send: [<Path key="a" d="M12 19V5.5" />, <Path key="b" d="m6 11 6-6 6 6" />],
  close: [<Path key="a" d="M6.5 6.5l11 11" />, <Path key="b" d="M17.5 6.5l-11 11" />],
  check: [<Path key="a" d="m5 12.5 4.5 4.5L19 7.5" />],
  plus: [<Path key="a" d="M12 5v14" />, <Path key="b" d="M5 12h14" />],
  minus: [<Path key="a" d="M5 12h14" />],
  back: [<Path key="a" d="m15 5-7 7 7 7" />],
  next: [<Path key="a" d="m9 5 7 7-7 7" />],
  retry: [<Path key="a" d="M4 12a8 8 0 1 0 2.4-5.7" />, <Path key="b" d="M4 4.5V9h4.5" />],
  home: [<Path key="a" d="m3.5 11 8.5-7.5 8.5 7.5" />, <Path key="b" d="M6 9.5V20h12V9.5" />],
  heart: [<Path key="a" d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z" />],
  bolt: [<Path key="a" d="M13 2.5 5 13.5h6.5l-1 8 8-11H12l1-8z" />],
  star: [<Path key="a" d="m12 3.5 2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.8l-5.2 2.8 1-5.8-4.3-4.1 5.9-.8L12 3.5z" />],
  bag: [<Path key="a" d="M5.5 8.5h13l-1 12h-11l-1-12z" />, <Path key="b" d="M9 8.5V7a3 3 0 0 1 6 0v1.5" />],
  tag: [<Path key="a" d="M3.5 12.5V4h8.5l8.5 8.5-8 8-9-8z" />, <Circle key="b" cx={8} cy={8.5} r={1.3} />],
  book: [<Path key="a" d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5v-15z" />, <Path key="b" d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19" />],
  spark: [<Path key="a" d="M12 3v5" />, <Path key="b" d="M12 16v5" />, <Path key="c" d="M3 12h5" />, <Path key="d" d="M16 12h5" />, <Path key="e" d="m6 6 2.5 2.5" />, <Path key="f" d="m15.5 15.5 2.5 2.5" />, <Path key="g" d="m6 18 2.5-2.5" />, <Path key="h" d="m15.5 8.5 2.5-2.5" />],
  play: [<Path key="a" d="M7.5 4.5v15l12-7.5-12-7.5z" />],
} as const;

export type IconName = keyof typeof SHAPES;

export function Icon({ name, size = 16, color = colors.fg.muted, width = 1.8 }: {
  name: IconName; size?: number; color?: string; width?: number;
}) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width}
      strokeLinecap="round" strokeLinejoin="round" pointerEvents="none">
      {SHAPES[name]}
    </Svg>
  );
}
