import { Text, View } from 'react-native';

import { Bar } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import type { Hero } from '@/types/domain';

type MeterTone = 'hp' | 'mp' | 'exp' | 'revival';

function Meter({ label, value, max, tone }: {
  label: string;
  value: number;
  max: number;
  tone: MeterTone;
}) {
  const color = toneColor[tone];
  return (
    <View className="flex-1 gap-1">
      <View className="flex-row items-baseline justify-between">
        <Text className="font-mono text-caption text-fg-subtle">{label}</Text>
        <Text
          numberOfLines={1}
          className="font-mono text-caption"
          style={{ color, fontVariant: ['tabular-nums'] }}
        >
          {value}/{max}
        </Text>
      </View>
      <Bar value={value} max={max} color={color} h={4} />
    </View>
  );
}

export function HeroStrip({ hero }: { hero: Hero }) {
  return (
    <View className="mx-5 px-3 py-1 flex-row gap-4">
      <Meter label="HP" value={hero.hp} max={hero.hpMax} tone="hp" />
      <Meter label="MP" value={hero.mp} max={hero.mpMax} tone="mp" />
      <Meter label="EXP" value={hero.exp} max={hero.expMax} tone="exp" />
      <Meter
        label="Revival"
        value={hero.reviveCoins}
        max={hero.reviveCoinsMax}
        tone="revival"
      />
    </View>
  );
}
