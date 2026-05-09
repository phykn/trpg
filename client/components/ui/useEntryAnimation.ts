import React from 'react';
import { Animated, Easing } from 'react-native';

export function useEntryAnimation() {
  const scale = React.useRef(new Animated.Value(1.04)).current;
  const opacity = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    Animated.parallel([
      Animated.timing(scale, {
        toValue: 1,
        duration: 220,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 220,
        useNativeDriver: true,
      }),
    ]).start();
  }, [scale, opacity]);

  return { scale, opacity };
}
