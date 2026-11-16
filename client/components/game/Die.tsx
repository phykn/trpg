import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, Platform, View } from 'react-native';

import { cn } from '@/design/ui';

const native = Platform.OS !== 'web';
// Which of the nine places in a 3 by 3 grid hold a pip, for each face.
const PIPS: Record<number, number[]> = { 1: [4], 2: [2, 6], 3: [2, 4, 6], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
const FLICK = 70;   // a new face this often while it tumbles

function otherFace(face: number) {
  const next = 1 + Math.floor(Math.random() * 5);
  return next >= face ? next + 1 : next;
}

// One die. While `rolling` it tumbles, hops and flicks through faces; when it stops it drops onto `face` with a bounce.
// `spin` sets which way it turns, so two dice do not move as one.
export function Die({ face, rolling, spin = 1, size = 64 }: { face: number; rolling: boolean; spin?: 1 | -1; size?: number }) {
  const [shown, setShown] = useState(face);
  const turn = useRef(new Animated.Value(0)).current;
  const hop = useRef(new Animated.Value(0)).current;
  const land = useRef(new Animated.Value(1)).current;
  const rolled = useRef(false);

  useEffect(() => {
    if (rolling) {
      rolled.current = true;
      const tumble = Animated.loop(Animated.parallel([
        Animated.timing(turn, { toValue: 1, duration: 360, easing: Easing.linear, useNativeDriver: native }),
        Animated.sequence([
          Animated.timing(hop, { toValue: 1, duration: 180, easing: Easing.out(Easing.quad), useNativeDriver: native }),
          Animated.timing(hop, { toValue: 0, duration: 180, easing: Easing.in(Easing.quad), useNativeDriver: native }),
        ]),
      ]));
      turn.setValue(0);
      tumble.start();
      const flick = setInterval(() => setShown(otherFace), FLICK);
      return () => { tumble.stop(); clearInterval(flick); };
    }
    setShown(face);
    if (rolled.current) {
      // Settle flat and squash in, like it hit the table.
      turn.setValue(0);
      hop.setValue(0);
      land.setValue(1.35);
      Animated.spring(land, { toValue: 1, friction: 4, tension: 160, useNativeDriver: native }).start();
    }
    return undefined;
  }, [rolling, face, turn, hop, land]);

  const rotate = turn.interpolate({ inputRange: [0, 1], outputRange: ['0deg', `${spin * 360}deg`] });
  const lift = hop.interpolate({ inputRange: [0, 1], outputRange: [0, -size / 4] });
  const cell = size / 3;
  const pip = Math.round(size * 0.17);
  return (
    <Animated.View style={{ width: size, height: size, transform: [{ translateY: lift }, { rotate }, { scale: land }] }}>
      <View accessibilityElementsHidden className={cn('h-full w-full rounded-xl border-2 border-fg-default bg-canvas-floating shadow-sm')}>
        {PIPS[shown].map((at) => (
          <View key={at} className="absolute rounded-full bg-fg-default"
            style={{ width: pip, height: pip, left: (at % 3) * cell + (cell - pip) / 2 - 2, top: Math.floor(at / 3) * cell + (cell - pip) / 2 - 2 }} />
        ))}
      </View>
    </Animated.View>
  );
}
