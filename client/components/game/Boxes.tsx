import { View } from 'react-native';

import { colors } from '@/design/tokens';

export function Boxes({ fill, boxes, fit = 0, next = 0, size = 8, tone = 'progress' }: {
  fill: number; boxes: number; fit?: number; next?: number; size?: number; tone?: 'progress' | 'danger' | 'time';
}) {
  const full = tone === 'danger' ? colors.box.danger : tone === 'time' ? colors.box.time : colors.box.full;
  return (
    <View className="flex-row items-center" style={{ gap: 2 }} accessibilityLabel={`${fill}/${boxes}`}>
      {Array.from({ length: boxes }, (_, i) => {
        const color = i < fill - fit ? full : i < fill ? colors.box.fit
          : i < fill + next ? colors.box.next : 'transparent';
        return (
          <View key={i} style={{
            width: size, height: size, borderRadius: 2, backgroundColor: color,
            borderWidth: 1, borderColor: i < fill + next ? color : colors.box.empty,
          }} />
        );
      })}
    </View>
  );
}
