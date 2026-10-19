import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { IconButton } from './Button';
import { Icon, type IconName } from './Icon';
import { useEnter } from './motion';
import { useDialog } from './useDialog';

// A card that rises from the bottom and covers only its own height, so the scene above stays readable.
export function Sheet({ title, icon, tone, onClose, children }: {
  title?: string; icon?: IconName; tone?: string; onClose?: () => void; children: ReactNode;
}) {
  const ref = useDialog(onClose);
  const enter = useEnter(24);
  return (
    <Animated.View style={enter}>
      <View ref={ref} accessibilityRole={'dialog' as never} aria-modal
        className="gap-3 rounded-t-2xl border-x border-t border-border-strong bg-canvas-floating px-4 pb-4 pt-3">
        <View className="min-h-[36px] flex-row items-center gap-2">
          {icon ? <Icon name={icon} size={18} color={tone ?? colors.gold.fg} /> : null}
          <Text accessibilityRole="header" className="min-w-0 flex-1 font-sans-semibold text-title text-fg-default">{title}</Text>
          {onClose ? <IconButton icon="close" label={ko.close} onPress={onClose} /> : null}
        </View>
        {children}
      </View>
    </Animated.View>
  );
}

// One row per answer: the same height, the same left edge, a chevron that says it goes on.
export function Choice({ label, sub, icon, primary, onPress }: {
  label: string; sub?: string; icon?: IconName; primary?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
      className={`min-h-[48px] flex-row items-center gap-3 rounded-xl px-4 py-2 ${primary ? 'bg-gold-fg' : 'border border-border-default bg-canvas-subtle'}`}>
      {icon ? <Icon name={icon} size={16} color={primary ? colors.fg['on-emphasis'] : colors.fg.muted} /> : null}
      <View className="min-w-0 flex-1">
        <Text className={`font-sans-semibold text-body ${primary ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{label}</Text>
        {sub ? <Text className="font-sans text-panel text-fg-muted">{sub}</Text> : null}
      </View>
      <Icon name="next" size={14} color={primary ? colors.fg['on-emphasis'] : colors.fg.subtle} />
    </Pressable>
  );
}
