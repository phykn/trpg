import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';
import { Bar } from './Bar';

export function StatRow({ label, value, max, color, display }: {
  label: string; value: number; max: number; color: string; display: string;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: Theme.space.sm, height: 16 }}>
      <Text style={{
        ...typeStyle('caption', { fontWeight: '600' as const, letterSpacing: 1.2 }),
        color: Theme.textFaint, minWidth: 28, textTransform: 'uppercase',
        fontFamily: Theme.fonts.sansSemibold,
      }}>{label}</Text>
      <View style={{ flex: 1 }}>
        <Bar value={value} max={max} color={color} bg={Theme.bgElev} />
      </View>
      <Text style={{
        ...typeStyle('caption', { fontWeight: '600' as const }),
        color: Theme.text,
        fontFamily: Theme.fonts.monoSemibold,
        fontVariant: ['tabular-nums'],
      }}>{display}</Text>
    </View>
  );
}
