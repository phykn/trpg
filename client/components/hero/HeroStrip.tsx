import { Text, View } from 'react-native';

import { Bar, Surface } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Hero } from '@/logic/hero/types';

type MeterTone = 'hp' | 'mp' | 'exp' | 'revival';

function Meter({ label, value, max, tone }: {
  label: string;
  value: number;
  max?: number;
  tone: MeterTone;
}) {
  const color = toneColor[tone];
  return (
    <View className="flex-1 gap-0.5">
      <View>
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
    <Surface className="mx-5 px-3 py-2 gap-2">
      <View className="flex-row items-start justify-between gap-3">
        <View className="flex-1 min-w-0">
          <Text numberOfLines={1} className="font-serif-medium text-title text-fg-default">
            {hero.name}
          </Text>
          <Text numberOfLines={1} className="font-sans text-caption text-fg-muted">
            {hero.raceJob || ko.hero.chip}
          </Text>
        </View>
        <View className="items-end">
          <Text className="font-sans text-caption text-fg-muted">{ko.hero.gold}</Text>
          <Text
            className="font-mono-semibold text-title text-fg-default"
            style={{ fontVariant: ['tabular-nums'] }}
          >
            {hero.gold}
          </Text>
        </View>
      </View>
      <View className="flex-row gap-3">
        <Meter label={ko.hero.hp} value={hero.hp} max={hero.hpMax} tone="hp" />
        <Meter label={ko.hero.mp} value={hero.mp} max={hero.mpMax} tone="mp" />
        <Meter label={ko.hero.exp} value={hero.exp} max={hero.expMax} tone="exp" />
        <Meter
          label={ko.hero.revive}
          value={hero.reviveCoins}
          max={hero.reviveCoinsMax}
          tone="revival"
        />
      </View>
    </Surface>
  );
}
