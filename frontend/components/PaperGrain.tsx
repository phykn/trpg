import { View } from 'react-native';
import Svg, { Defs, Pattern, Rect, Circle } from 'react-native-svg';

import { colors } from '@/design/tokens';

const TILE = 120;
const DOTS_PER_TILE = 56;
const SEED = 42;

function makeDots() {
  let s = SEED | 0;
  const next = () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return Array.from({ length: DOTS_PER_TILE }, () => ({
    cx: next() * TILE,
    cy: next() * TILE,
    r: 0.35 + next() * 0.55,
    o: 0.18 + next() * 0.45,
  }));
}

const DOTS = makeDots();

export function PaperGrain() {
  return (
    <View
      pointerEvents="none"
      style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
    >
      <Svg width="100%" height="100%">
        <Defs>
          <Pattern
            id="paper-grain"
            x={0}
            y={0}
            width={TILE}
            height={TILE}
            patternUnits="userSpaceOnUse"
          >
            {DOTS.map((d, i) => (
              <Circle
                key={i}
                cx={d.cx}
                cy={d.cy}
                r={d.r}
                fill={colors.fg.default}
                opacity={d.o * 0.07}
              />
            ))}
          </Pattern>
        </Defs>
        <Rect width="100%" height="100%" fill="url(#paper-grain)" />
      </Svg>
    </View>
  );
}
