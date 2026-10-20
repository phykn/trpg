import { useEffect, useRef } from 'react';
import { View } from 'react-native';
import Animated, {
  useAnimatedStyle, useReducedMotion, useSharedValue, withSequence, withTiming,
} from 'react-native-reanimated';

import { colors } from '@/design/tokens';

function Box({ on, color, size, part = 0 }: { on: boolean; color: string; size: number; part?: number }) {
  const reduced = useReducedMotion();
  const was = useRef(on);
  const scale = useSharedValue(1);
  useEffect(() => {
    // A box that fills now swells once, so the eye finds what changed.
    if (on && !was.current && !reduced) scale.value = withSequence(withTiming(1.35, { duration: 120 }), withTiming(1, { duration: 180 }));
    was.current = on;
  }, [on, reduced, scale]);
  const style = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));
  return (
    <Animated.View style={[{
      width: size, height: size, borderRadius: 2, borderWidth: 1, overflow: 'hidden',
      backgroundColor: on ? color : 'transparent', borderColor: on ? color : colors.box.empty,
    }, style]}>
      {!on && part > 0 ? (
        <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: `${Math.round(part * 100)}%`, backgroundColor: color, opacity: 0.5 }} />
      ) : null}
    </Animated.View>
  );
}

// `part` fills the next box from the bottom: how far time has run toward it.
export function Boxes({ fill, boxes, size = 8, tone = 'progress', part = 0 }: {
  fill: number; boxes: number; size?: number; tone?: 'progress' | 'danger'; part?: number;
}) {
  const color = tone === 'danger' ? colors.box.danger : colors.box.full;
  return (
    <View className="flex-row items-center" style={{ gap: 2 }} accessibilityLabel={`${fill}/${boxes}`}>
      {Array.from({ length: boxes }, (_, i) => <Box key={i} on={i < fill} color={color} size={size} part={i === fill ? part : 0} />)}
    </View>
  );
}
