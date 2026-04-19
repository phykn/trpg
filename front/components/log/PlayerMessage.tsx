import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';

export function PlayerMessage({ text }: { text: string }) {
  return (
    <View style={{
      alignSelf: 'flex-end', maxWidth: '82%',
      paddingVertical: Theme.space.sm + 2, paddingHorizontal: Theme.space.md + 2,
      backgroundColor: Theme.accentSoft,
      borderRadius: Theme.radius.md, borderBottomRightRadius: 6,
    }}>
      <Text style={{
        color: Theme.accent, fontFamily: Theme.fonts.monoMedium,
        ...typeStyle('title', { fontWeight: '500' as const }),
      }}>{text}</Text>
    </View>
  );
}
