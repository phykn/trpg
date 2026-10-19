import { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';

import { colors, motion } from '@/design/tokens';
import type { Preview } from '@/services/types';

const ORDER = ['fail', 'mixed', 'success'] as const;

export function OddsBar({ odds }: { odds: Preview['odds'] }) {
  const widths = useRef(ORDER.map((k) => new Animated.Value(odds[k]))).current;
  useEffect(() => {
    Animated.parallel(ORDER.map((k, i) => Animated.timing(widths[i], {
      toValue: odds[k], duration: motion.odds, useNativeDriver: false,
    }))).start();
  }, [odds, widths]);
  return (
    <View className="h-[6px] flex-row overflow-hidden rounded-full" accessibilityRole="progressbar">
      {ORDER.map((k, i) => (
        <Animated.View key={k} style={{
          flexGrow: widths[i], flexBasis: 0, backgroundColor: colors.band[k], minWidth: odds[k] > 0 ? 2 : 0,
        }} />
      ))}
    </View>
  );
}
