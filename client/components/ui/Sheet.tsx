import { type ReactNode, useEffect } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';

import { colors, icon as iconSize, motion } from '@/design/tokens';
import { control, surface, text, tone } from '@/design/ui';
import { ko } from '@/locale/ko';
import { IconButton, pressed } from './Button';
import { Icon, type IconName } from './Icon';
import { useDialog } from './useDialog';

// A card that rises from the bottom and covers only its own height, so the scene above stays readable; `full` fills its parent.
export function Sheet({ title, icon, full, onClose, children }: {
  title?: string; icon?: IconName; full?: boolean; onClose?: () => void; children: ReactNode;
}) {
  const ref = useDialog(onClose);
  const reduced = useReducedMotion();
  const shown = useSharedValue(reduced ? 1 : 0);
  useEffect(() => {
    if (!reduced) shown.value = withTiming(1, { duration: motion.enter, easing: Easing.out(Easing.cubic) });
  }, [reduced, shown]);
  const enter = useAnimatedStyle(() => ({ opacity: shown.value, transform: [{ translateY: (1 - shown.value) * 24 }] }));
  return (
    <Animated.View style={[enter, full ? { flex: 1, minHeight: 0 } : null]}>
      <View ref={ref} accessibilityRole={'dialog' as never} aria-modal
        className={`gap-3 ${surface.sheet} ${full ? 'min-h-0 flex-1' : ''}`}>
        <View className="min-h-9 flex-row items-center gap-2">
          {icon ? <Icon name={icon} size={iconSize.lg} color={colors.gold.fg} /> : null}
          {title ? (
            <Text accessibilityRole="header" className={`min-w-0 flex-1 ${text.title}`}>{title}</Text>
          ) : <View className="flex-1" />}
          {onClose ? <IconButton icon="close" label={ko.close} onPress={onClose} /> : null}
        </View>
        {children}
      </View>
    </Animated.View>
  );
}

// One row per answer: the same height, the same left edge, a chevron that says it goes on.
export function Choice({ label, sub, primary, onPress }: {
  label: string; sub?: string; primary?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={sub ? `${label}, ${sub}` : label} onPress={onPress}
      style={pressed}
      className={`${control.row} ${primary ? tone.picked : tone.quiet}`}>
      <View className="min-w-0 flex-1">
        <Text className={primary ? text.strongOn : text.strong}>{label}</Text>
        {sub ? <Text className={primary ? text.subOn : text.sub}>{sub}</Text> : null}
      </View>
      <Icon name="next" size={iconSize.sm} color={primary ? colors.fg['on-emphasis'] : colors.fg.subtle} />
    </Pressable>
  );
}
