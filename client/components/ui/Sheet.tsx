import { type ReactNode, useEffect } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useReducedMotion, useSharedValue, withTiming } from 'react-native-reanimated';

import { colors, motion } from '@/design/tokens';
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
        className={`gap-3 rounded-t-2xl border-x border-t border-border-strong bg-canvas-floating px-4 pb-4 pt-3 ${full ? 'min-h-0 flex-1' : ''}`}>
        <View className="min-h-[36px] flex-row items-center gap-2">
          {icon ? <Icon name={icon} size={18} color={colors.gold.fg} /> : null}
          {title ? (
            <Text accessibilityRole="header" className="min-w-0 flex-1 font-sans-semibold text-title text-fg-default">{title}</Text>
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
      className={`min-h-[48px] flex-row items-center gap-3 rounded-xl px-4 py-2 ${primary ? 'bg-gold-fg' : 'border border-border-default bg-canvas-subtle'}`}>
      <View className="min-w-0 flex-1">
        <Text className={`font-sans-semibold text-body ${primary ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{label}</Text>
        {sub ? <Text className={`font-sans text-panel ${primary ? 'text-fg-on-emphasis opacity-80' : 'text-fg-muted'}`}>{sub}</Text> : null}
      </View>
      <Icon name="next" size={14} color={primary ? colors.fg['on-emphasis'] : colors.fg.subtle} />
    </Pressable>
  );
}
