import { type ReactNode, useEffect } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';

import { colors, icon as iconSize, motion } from '@/design/tokens';
import { control, surface, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import { IconButton, pressed } from './Button';
import { Icon } from './Icon';
import { useDialog } from './useDialog';

// A card that rises from the bottom and covers only its own height, so the scene above stays readable; `full` fills its parent.
export function Sheet({ title, full, onClose, children }: {
  title?: string; full?: boolean; onClose?: () => void; children: ReactNode;
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
        className={surface({ kind: 'sheet' }, 'gap-3', full && 'min-h-0 flex-1')}>
        <SheetHeader title={title} onClose={onClose} />
        {children}
      </View>
    </Animated.View>
  );
}

// The title and the close button, the same on every sheet.
export function SheetHeader({ title, onClose }: { title?: string; onClose?: () => void }) {
  return (
    <View className="min-h-9 flex-row items-center gap-2">
      {title ? (
        <Text accessibilityRole="header" className={text({ kind: 'title' }, 'min-w-0 flex-1')}>{title}</Text>
      ) : <View className="flex-1" />}
      {onClose ? <IconButton icon="close" label={ko.close} onPress={onClose} /> : null}
    </View>
  );
}

// One row per answer: the same height, the same left edge, a chevron that says it goes on.
export function Choice({ label, sub, primary, onPress }: {
  label: string; sub?: string; primary?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={sub ? `${label}, ${sub}` : label} onPress={onPress}
      style={pressed}
      className={control({ kind: 'row', tone: primary ? 'picked' : 'quiet' })}>
      <View className="min-w-0 flex-1">
        <Text className={text({ kind: 'strong', on: primary })}>{label}</Text>
        {sub ? <Text className={text({ kind: 'sub', on: primary })}>{sub}</Text> : null}
      </View>
      <Icon name="next" size={iconSize.sm} color={primary ? colors.fg['on-emphasis'] : colors.fg.subtle} />
    </Pressable>
  );
}
