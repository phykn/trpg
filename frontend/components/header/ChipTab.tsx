import { Text, Pressable, View } from 'react-native';
import { colors } from '@/design/tokens';
import type { PanelSlot } from '@/types/ui';

export function ChipTab({ chip, active, onPress }: {
  chip: PanelSlot['chip'];
  active: boolean;
  onPress: () => void;
}) {
  const bg = active ? 'bg-canvas-inset' : 'bg-transparent';
  const fontWeight = active ? 'font-sans-semibold' : 'font-sans-medium';
  const color = active ? 'text-fg-default' : 'text-fg-muted';

  return (
    <Pressable
      onPress={onPress}
      className={`flex-1 min-w-0 h-8 px-2 flex-row items-center justify-center gap-1.5 rounded-sm ${bg}`}
    >
      <Text numberOfLines={1} className={`text-caption ${fontWeight} ${color}`}>
        {chip.short}
      </Text>
      {active && (
        <View
          style={{
            position: 'absolute',
            bottom: 0,
            left: 8,
            right: 8,
            height: 2,
            backgroundColor: colors.accent.fg,
          }}
        />
      )}
    </Pressable>
  );
}
