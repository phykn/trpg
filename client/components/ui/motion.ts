import { useEffect } from 'react';
import {
  Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withDelay, withTiming,
} from 'react-native-reanimated';

import { motion } from '@/design/tokens';

const ease = Easing.out(Easing.cubic);

// Chat lines, sheets, dropdowns and screens arrive the same way: a short fade with a small travel from `from` px.
export function useEnter(from = 8, delay = 0) {
  const reduced = useReducedMotion();
  const t = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) t.value = withDelay(delay, withTiming(1, { duration: motion.enter, easing: ease }));
  }, [reduced, delay, t]);
  return useAnimatedStyle(() => ({
    opacity: t.value,
    transform: [{ translateY: (1 - t.value) * from }],
  }));
}
