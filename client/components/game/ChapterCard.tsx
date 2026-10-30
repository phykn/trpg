import { useEffect } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, {
  Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withDelay, withSequence, withTiming,
} from 'react-native-reanimated';

import { colors, motion } from '@/design/tokens';
import { ko } from '@/locale/ko';

// A chapter opens on its own title once, then gets out of the way; a tap ends it early (ui.md 5.6).
export function ChapterCard({ k, title, aim, onDone }: { k: number; title: string; aim: string; onDone: () => void }) {
  const reduced = useReducedMotion();
  const t = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    const id = setTimeout(onDone, motion.chapterIn + motion.chapterHold + motion.chapterOut);
    if (!reduced) {
      t.value = withSequence(withTiming(1, { duration: motion.chapterIn, easing: Easing.out(Easing.cubic) }),
        withDelay(motion.chapterHold, withTiming(2, { duration: motion.chapterOut, easing: Easing.in(Easing.cubic) })));
    }
    return () => clearTimeout(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const fade = useAnimatedStyle(() => ({ opacity: t.value <= 1 ? t.value : 2 - t.value }));
  const rise = useAnimatedStyle(() => ({ transform: [{ translateY: (1 - Math.min(t.value, 1)) * 12 }] }));
  return (
    <View className="absolute bottom-0 left-0 right-0 top-0 z-40">
      <Animated.View style={[{ flex: 1, backgroundColor: colors.canvas.default }, fade]}>
        <Pressable accessibilityLabel={ko.skip} onPress={onDone} className="flex-1 items-center justify-center px-8">
          <Animated.View style={rise}>
            <View className="items-center gap-3">
              <Text className="font-sans-semibold text-title text-gold-fg">{ko.chapterNo(k)}</Text>
              <Text accessibilityRole="header" className="text-center font-serif text-display text-fg-default">{title}</Text>
              <View className="h-[1px] w-10 bg-gold-fg" />
              <Text className="text-center font-sans text-body text-fg-muted">{aim}</Text>
            </View>
          </Animated.View>
        </Pressable>
      </Animated.View>
    </View>
  );
}
