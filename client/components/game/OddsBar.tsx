import { useEffect, useRef } from 'react';
import { Animated, Text, View } from 'react-native';

import { colors, motion } from '@/design/tokens';
import { ko } from '@/locale/ko';
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
    <View className="h-7 flex-row overflow-hidden rounded-md" accessibilityRole="progressbar">
      {ORDER.map((k, i) => (
        <Animated.View key={k} className="justify-center px-1" style={{
          flexGrow: widths[i], flexBasis: 0, backgroundColor: colors.band[k], minWidth: odds[k] > 0 ? 2 : 0,
        }}>
          <Text numberOfLines={1} className="font-sans text-chip text-fg-default">{ko.odds(ko.result[k], odds[k])}</Text>
        </Animated.View>
      ))}
    </View>
  );
}
