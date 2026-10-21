import { useEffect, useRef, useState } from 'react';
import { Pressable, View } from 'react-native';
import Animated, {
  cancelAnimation, Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withRepeat, withSequence, withTiming,
} from 'react-native-reanimated';

import { colors, motion } from '@/design/tokens';

const PIPS: Record<number, [number, number][]> = {
  1: [[1, 1]], 2: [[0, 0], [2, 2]], 3: [[0, 0], [1, 1], [2, 2]], 4: [[0, 0], [0, 2], [2, 0], [2, 2]],
  5: [[0, 0], [0, 2], [1, 1], [2, 0], [2, 2]], 6: [[0, 0], [0, 2], [1, 0], [1, 2], [2, 0], [2, 2]],
};

// Value 0 is a blank die: one not rolled yet, so its pips cannot be mistaken for a result.
export function Face({ value, size = 44, dim, ring }: { value: number; size?: number; dim?: boolean; ring?: string }) {
  const pip = Math.max(2, Math.round(size * 0.18));
  const edge = Math.round(size * 0.15);
  const step = (size - 2 * edge - pip) / 2;
  return (
    <View className="bg-fg-default" style={{
      width: size, height: size, borderRadius: Math.round(size * 0.22), opacity: dim ? 0.4 : 1,
      borderWidth: ring ? 2 : 0, borderColor: ring,
    }}>
      {(PIPS[value] ?? []).map(([r, c]) => (
        <View key={`${r}${c}`} className="absolute rounded-full bg-canvas-default"
          style={{ width: pip, height: pip, top: edge + r * step, left: edge + c * step }} />
      ))}
    </View>
  );
}

// A die tumbles until its value arrives, then lands with one small bump.
function Die({ value, tumbling, spin, ready }: { value: number | null; tumbling: boolean; spin: 1 | -1; ready: boolean }) {
  const reduced = useReducedMotion();
  const turn = useSharedValue(0);
  const scale = useSharedValue(1);
  const [face, setFace] = useState(0);
  const landed = useRef(value != null);

  useEffect(() => {
    if (!tumbling || reduced) return undefined;
    landed.current = false;
    const id = setInterval(() => setFace(1 + Math.floor(Math.random() * 6)), 70);
    turn.value = withRepeat(withTiming(spin * 360, { duration: 420, easing: Easing.linear }), -1, false);
    // Stopping with no value (a lost answer) leaves a blank die upright, not a random face that reads as a result.
    return () => { clearInterval(id); setFace(0); turn.value = withTiming(0, { duration: 160, easing: Easing.out(Easing.cubic) }); };
  }, [tumbling, reduced, spin, turn]);

  useEffect(() => {
    if (value == null || landed.current) return;
    landed.current = true;
    if (reduced) return;
    scale.value = withSequence(withTiming(1.12, { duration: 110 }), withTiming(1, { duration: 170 }));
  }, [value, reduced, turn, scale]);

  const style = useAnimatedStyle(() => ({ transform: [{ rotate: `${turn.value % 360}deg` }, { scale: scale.value }] }));
  return <Animated.View style={style}><Face value={value ?? face} ring={ready ? colors.gold.fg : undefined} /></Animated.View>;
}

export function Dice({ state, values, onRelease, label }: {
  state: 'ready' | 'rolling' | 'stopped' | 'gone';
  values: [number | null, number | null];
  onRelease?: () => void;
  label: string;
}) {
  const reduced = useReducedMotion();
  const sway = useSharedValue(0);
  const breath = useSharedValue(1);
  const held = useRef(0);

  // Waiting dice are blank, ringed in gold and breathing: together they say "press me" without words.
  useEffect(() => {
    if (state !== 'ready' || reduced) return undefined;
    breath.value = withRepeat(withSequence(withTiming(1.05, { duration: 900, easing: Easing.inOut(Easing.sin) }),
      withTiming(1, { duration: 900, easing: Easing.inOut(Easing.sin) })), -1);
    return () => { cancelAnimation(breath); breath.value = withTiming(1, { duration: 120 }); };
  }, [state, reduced, breath]);

  const style = useAnimatedStyle(() => ({ transform: [{ rotate: `${sway.value}deg` }, { scale: breath.value }] }));

  const press = () => {
    if (state !== 'ready') return;
    held.current = Date.now();
    if (!reduced) {
      sway.value = withRepeat(withSequence(withTiming(-4, { duration: 70 }), withTiming(4, { duration: 70 })), -1, true);
    }
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate?.(10);
  };
  // The roll goes on press (a click on web): press-out alone is lost when the browser reports touch support.
  const release = () => {
    if (state !== 'ready') return;
    const strength = held.current ? Math.min(Date.now() - held.current, motion.shakeMax) / motion.shakeMax : 0;
    held.current = 0;
    cancelAnimation(sway);
    sway.value = withTiming(0, { duration: 80 + 120 * strength });
    onRelease?.();
  };

  // Rolling dice tumble until their value arrives; stopped dice rest, blank if they have none.
  const tumbling = (i: 0 | 1) => state === 'rolling' && values[i] == null;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={state !== 'ready'}
      onPressIn={press} onPress={release} className="rounded-2xl p-2">
      <Animated.View style={[{ flexDirection: 'row', gap: 12, opacity: state === 'gone' ? 0 : 1 }, style]}>
        <Die value={values[0]} tumbling={tumbling(0)} spin={1} ready={state === 'ready'} />
        <Die value={values[1]} tumbling={tumbling(1)} spin={-1} ready={state === 'ready'} />
      </Animated.View>
    </Pressable>
  );
}
