import { Text, View } from 'react-native';

import { Bar, Surface } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { Hero } from '@/logic/hero/types';

type MeterTone = 'hp' | 'mp' | 'exp' | 'revival';
type MeterDisplayMode = 'fraction' | 'percent' | 'current';

export function meterDisplay(
  value: number,
  max?: number,
  mode: MeterDisplayMode = 'fraction',
): string {
  if (mode === 'current' || max === undefined) {
    return `${value}`;
  }
  if (mode === 'percent') {
    const pct = max > 0 ? Math.round((value / max) * 100) : 0;
    return `${Math.min(100, Math.max(0, pct))}%`;
  }
  return `${value}/${max}`;
}

function Meter({ label, value, max, tone, display = 'fraction' }: {
  label: string;
  value: number;
  max?: number;
  tone: MeterTone;
  display?: MeterDisplayMode;
}) {
  const color = toneColor[tone];
  return (
    <View className="flex-1 gap-0.5">
      <View className="flex-row items-center justify-between gap-2">
        <Text numberOfLines={1} className="font-sans-medium text-caption text-fg-subtle">
          {label}
        </Text>
        <Text
          numberOfLines={1}
          className="font-mono text-caption"
          style={{ color, fontVariant: ['tabular-nums'] }}
        >
          {meterDisplay(value, max, display)}
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
    <Surface className="mx-5 px-3 py-2">
      <View className="flex-row gap-3">
        <Meter label={ko.hero.hp} value={hero.hp} max={hero.hpMax} tone="hp" />
        <Meter label={ko.hero.mp} value={hero.mp} max={hero.mpMax} tone="mp" />
        <Meter
          label={ko.hero.exp}
          value={hero.exp}
          max={hero.expMax}
          tone="exp"
          display="percent"
        />
        <Meter
          label={ko.hero.revive}
          value={hero.reviveCoins}
          max={hero.reviveCoinsMax}
          tone="revival"
          display="current"
        />
      </View>
    </Surface>
  );
}
