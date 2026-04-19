import { View } from 'react-native';

export function Bar({ value, max, color, bg, h = 4, radius = 999 }: {
  value: number; max: number; color: string; bg: string; h?: number; radius?: number;
}) {
  const pct = Math.max(0, Math.min(1, value / max)) * 100;
  return (
    <View style={{ width: '100%', height: h, backgroundColor: bg, borderRadius: radius, overflow: 'hidden' }}>
      <View style={{ width: `${pct}%`, height: '100%', backgroundColor: color, borderRadius: radius }} />
    </View>
  );
}
