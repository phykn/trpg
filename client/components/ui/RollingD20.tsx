import React from 'react';
import { Animated, Easing, Text, View } from 'react-native';

import { colors } from '@/design/tokens';

export function RollingD20({
  value = 20,
  label,
  detail,
}: {
  value?: number;
  label: string;
  detail?: string;
}) {
  const motion = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(motion, {
          toValue: 1,
          duration: 360,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(motion, {
          toValue: 0,
          duration: 520,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [motion]);

  const translateX = motion.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0, 7, -3],
  });
  const rotate = motion.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: ['-10deg', '16deg', '-5deg'],
  });

  return (
    <View className="flex-row items-center gap-3">
      <Animated.View
        accessibilityLabel={label}
        className="h-14 w-14 items-center justify-center rounded-xl border border-accent-fg bg-canvas-inset"
        style={{
          opacity: 0.98,
          transform: [{ translateX }, { rotate }],
        }}
      >
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            width: 31,
            height: 31,
            borderWidth: 1,
            borderColor: `${colors.fg.default}26`,
            transform: [{ rotate: '45deg' }],
          }}
        />
        <View
          pointerEvents="none"
          style={{
            position: 'absolute',
            width: 18,
            height: 18,
            borderWidth: 1,
            borderColor: `${colors.fg.default}16`,
            transform: [{ rotate: '45deg' }],
          }}
        />
        <Text className="font-mono-semibold text-title text-fg-default">
          {value}
        </Text>
      </Animated.View>
      <View className="flex-1 min-w-0">
        <Text className="font-sans-bold text-panel text-fg-default" numberOfLines={1}>
          {label}
        </Text>
        {detail ? (
          <Text className="font-sans-medium text-caption text-fg-muted" numberOfLines={2}>
            {detail}
          </Text>
        ) : null}
      </View>
    </View>
  );
}
