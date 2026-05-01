import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import type { PanelSlot } from '@/types/ui';

export function ChipTab({ chip, active, onPress }: {
  chip: PanelSlot['chip'];
  active: boolean;
  onPress: () => void;
}) {
  const bg = active ? 'bg-accent-muted' : 'bg-transparent active:bg-canvas-inset';
  const fontWeight = active ? 'font-sans-semibold' : 'font-sans-medium';
  const color = active ? 'text-accent-fg' : 'text-fg-muted';

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={chip.short}
      accessibilityState={{ selected: active }}
      className={`flex-1 min-w-0 h-8 px-2 flex-row items-center justify-center gap-1.5 rounded-sm ${bg}`}
    >
      <Text numberOfLines={1} className={`text-caption ${fontWeight} ${color}`}>
        {chip.short}
      </Text>
      {chip.dot && (
        <View
          style={{
            position: 'absolute',
            top: 6,
            right: 6,
            width: 6,
            height: 6,
            borderRadius: 3,
            backgroundColor: colors.accent.fg,
          }}
        />
      )}
    </Pressable>
  );
}
