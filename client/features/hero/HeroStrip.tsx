import { Text, View } from 'react-native';

import { Bar, Surface } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import type { Hero } from './types';

type MeterTone = 'hp' | 'mp' | 'exp' | 'revival' | 'gold';

function Meter({ label, value, max, tone }: {
  label: string;
  value: number;
  max?: number;
  tone: MeterTone;
}) {
  const color = toneColor[tone];
  return (
    <View className="flex-1 gap-1">
      <View className="flex-row items-baseline justify-between">
        <Text className="font-sans-medium text-caption text-fg-subtle">{label}</Text>
        <Text
          numberOfLines={1}
          className="font-mono text-caption"
          style={{ color, fontVariant: ['tabular-nums'] }}
        >
          {max !== undefined ? `${value}/${max}` : value}
        </Text>
      </View>
      {max !== undefined ? (
        <Bar value={value} max={max} color={color} h={4} />
      ) : (
        <View className="h-1" />
      )}
    </View>
  );
}

export function HeroStrip({ hero }: { hero: Hero }) {
  return (
    <Surface className="mx-5 px-3 py-1 flex-row gap-3">
      <Meter label="체력" value={hero.hp} max={hero.hpMax} tone="hp" />
      <Meter label="마나" value={hero.mp} max={hero.mpMax} tone="mp" />
      <Meter label="경험" value={hero.exp} max={hero.expMax} tone="exp" />
      <Meter
        label="소생"
        value={hero.reviveCoins}
        max={hero.reviveCoinsMax}
        tone="revival"
      />
      <Meter label="금화" value={hero.gold} tone="gold" />
    </Surface>
  );
}
