import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';

export function InlineNodes({ entries }: { entries: [string, string | number][] }) {
  return (
    <View style={{
      flex: 1, minWidth: 0,
      flexDirection: 'row', justifyContent: 'space-between', gap: Theme.space.xs,
    }}>
      {entries.map(([k, v]) => (
        <View key={k} style={{ flexDirection: 'row', gap: 4 }}>
          <Text style={{
            ...typeStyle('caption'),
            color: Theme.textFaint, fontFamily: Theme.fonts.monoRegular,
            fontVariant: ['tabular-nums'],
          }}>{k}</Text>
          <Text style={{
            ...typeStyle('caption'),
            color: Theme.text, fontFamily: Theme.fonts.monoRegular,
            fontVariant: ['tabular-nums'], minWidth: 16, textAlign: 'right',
          }}>{String(v)}</Text>
        </View>
      ))}
    </View>
  );
}
