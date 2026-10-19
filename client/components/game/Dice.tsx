import { useEffect, useRef, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, {
  cancelAnimation, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withSequence, withTiming,
} from 'react-native-reanimated';

import { motion } from '@/design/tokens';

const PIPS: Record<number, [number, number][]> = {
  1: [[1, 1]], 2: [[0, 0], [2, 2]], 3: [[0, 0], [1, 1], [2, 2]], 4: [[0, 0], [0, 2], [2, 0], [2, 2]],
  5: [[0, 0], [0, 2], [1, 1], [2, 0], [2, 2]], 6: [[0, 0], [0, 2], [1, 0], [1, 2], [2, 0], [2, 2]],
};

function Face({ value, dim }: { value: number; dim?: boolean }) {
  return (
    <View className="h-11 w-11 rounded-lg border border-border-strong bg-fg-default" style={{ opacity: dim ? 0.4 : 1 }}>
      {PIPS[value].map(([r, c]) => (
        <View key={`${r}${c}`} className="absolute h-2 w-2 rounded-full bg-canvas-default"
          style={{ top: 6 + r * 12, left: 6 + c * 12 }} />
      ))}
    </View>
  );
}

/** Two dice: shake while held, tumble while the answer is on its way, stop on the server's values. */
export function Dice({ state, values, onRelease, label }: {
  state: 'ready' | 'rolling' | 'stopped' | 'gone' | 'locked';
  values: [number | null, number | null];
  onRelease?: () => void;
  label: string;
}) {
  const reduced = useReducedMotion();
  const tilt = useSharedValue(0);
  const [faces, setFaces] = useState<[number, number]>([1, 1]);
  const held = useRef(0);

  useEffect(() => {
    if (state !== 'rolling' || reduced) return undefined;
    const id = setInterval(() => setFaces([1 + Math.floor(Math.random() * 6), 1 + Math.floor(Math.random() * 6)]), 80);
    tilt.value = withRepeat(withSequence(withTiming(-12, { duration: 90 }), withTiming(12, { duration: 90 })), -1, true);
    return () => { clearInterval(id); cancelAnimation(tilt); tilt.value = withTiming(0, { duration: 120 }); };
  }, [state, reduced, tilt]);

  const style = useAnimatedStyle(() => ({ transform: [{ rotate: `${tilt.value}deg` }] }));
  const shown: [number, number] = [values[0] ?? faces[0], values[1] ?? faces[1]];

  const press = () => {
    if (state !== 'ready') return;
    held.current = Date.now();
    if (!reduced) {
      tilt.value = withRepeat(withSequence(withTiming(-4, { duration: 70 }), withTiming(4, { duration: 70 })), -1, true);
    }
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate?.(10);
  };
  // The roll goes on press (a click on web): press-out alone is lost when the browser reports touch support.
  const release = () => {
    if (state !== 'ready') return;
    const strength = held.current ? Math.min(Date.now() - held.current, motion.shakeMax) / motion.shakeMax : 0;
    held.current = 0;
    cancelAnimation(tilt);
    tilt.value = withTiming(0, { duration: 80 + 120 * strength });
    onRelease?.();
  };

  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={state !== 'ready'}
      onPressIn={press} onPress={release} className="flex-row items-center gap-3">
      <Animated.View style={[{ flexDirection: 'row', gap: 8, opacity: state === 'gone' ? 0 : 1 }, style]}>
        <Face value={shown[0]} dim={state === 'locked'} />
        <Face value={shown[1]} dim={state === 'locked'} />
      </Animated.View>
      {state === 'ready' ? <Text className="font-sans text-panel text-fg-muted">{label}</Text> : null}
    </Pressable>
  );
}
