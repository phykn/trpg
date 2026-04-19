import React from 'react';
import { View, Text, Pressable } from 'react-native';
import { Bar } from '@/components/ui';
import { HeroDetail } from './HeroDetail';
import { toneColor } from '@/design/tokens';
import type { Hero } from '@/types/domain';

type MeterTone = 'hp' | 'mp' | 'exp';

function Column({ top, bottom, paddingRight }: {
  top: React.ReactNode;
  bottom: React.ReactNode;
  paddingRight?: number;
}) {
  return (
    <View className="flex-1 gap-1" style={{ paddingRight }}>
      <View className="h-3.5 justify-center">{top}</View>
      <View className="h-3.5 justify-center">{bottom}</View>
    </View>
  );
}

function Identity({ name, level }: { name: string; level: number }) {
  return (
    <Column
      top={
        <Text numberOfLines={1} className="font-sans-semibold text-caption text-fg-default">
          {name}
        </Text>
      }
      bottom={
        <Text numberOfLines={1} className="font-sans-medium text-caption text-fg-muted">
          Lv {level}
        </Text>
      }
    />
  );
}

function Meter({ label, value, max, tone }: {
  label: string; value: number; max: number; tone: MeterTone;
}) {
  const color = toneColor[tone];
  return (
    <Column
      paddingRight={8}
      top={
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
      }
      bottom={<Bar value={value} max={max} color={color} h={4} />}
    />
  );
}

export function HeroPill({ hero, expanded, onToggle }: {
  hero: Hero;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <View className="mx-5">
      <Pressable
        onPress={onToggle}
        className="bg-canvas-subtle border border-border-default rounded-md py-2 px-3 flex-row items-center gap-3"
      >
        <Identity name={hero.name} level={hero.level} />
        <Meter label="HP"  value={hero.hp}  max={hero.hpMax}  tone="hp" />
        <Meter label="MP"  value={hero.mp}  max={hero.mpMax}  tone="mp" />
        <Meter label="EXP" value={hero.exp} max={hero.expMax} tone="exp" />
      </Pressable>

      {expanded && <HeroDetail hero={hero} />}
    </View>
  );
}
