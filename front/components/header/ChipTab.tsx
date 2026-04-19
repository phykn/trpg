import { View, Text, Pressable } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import type { PanelSlot } from '@/types/game';

export function ChipTab({ chip, active, onPress }: {
  chip: PanelSlot['chip']; active: boolean; onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={{
      flex: 1, minWidth: 0, height: 28, paddingHorizontal: Theme.space.sm,
      backgroundColor: active ? Theme.bgElev : 'transparent',
      borderRadius: Theme.radius.sm - 2,
      flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    }}>
      <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: chip.dot, flexShrink: 0 }} />
      <Text numberOfLines={1} style={{
        ...typeStyle('caption', { fontWeight: (active ? '600' : '500') as '600' | '500' }),
        color: active ? Theme.text : Theme.textDim,
        fontFamily: active ? Theme.fonts.sansSemibold : Theme.fonts.sansMedium,
      }}>{chip.short}</Text>
    </Pressable>
  );
}
