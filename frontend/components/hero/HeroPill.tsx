import React from 'react';
import { View, Text, Pressable } from 'react-native';
import { Bar } from '@/components/ui';
import { HeroDetail } from './HeroDetail';
import { colors, shadow, toneColor } from '@/design/tokens';
import type { Hero } from '@/types/domain';

type MeterTone = 'hp' | 'mp' | 'exp';

function Column({ top, bottom, paddingRight, flex = 1 }: {
  top: React.ReactNode;
  bottom: React.ReactNode;
  paddingRight?: number;
  flex?: number;
}) {
  return (
    <View className="gap-1" style={{ paddingRight, flex }}>
      <View className="h-3.5 justify-center">{top}</View>
      <View className="h-3.5 justify-center">{bottom}</View>
    </View>
  );
}

function Identity({ name, level, canLevelUp }: { name: string; level: number; canLevelUp: boolean }) {
  return (
    <Column
      flex={1.4}
      paddingRight={8}
      top={
        <Text numberOfLines={1} className="font-sans-semibold text-caption text-fg-default">
          {name}
        </Text>
      }
      bottom={
        <View className="flex-row items-center gap-1">
          <Text numberOfLines={1} className="font-sans-medium text-caption text-fg-muted">
            Lv {level}
          </Text>
          {canLevelUp && (
            <View
              className="px-1.5 rounded-full"
              style={{ backgroundColor: `${colors.accent.fg}26`, paddingVertical: 1 }}
            >
              <Text className="font-sans-bold text-meta text-accent-fg" style={{ lineHeight: 12 }}>
                ↑
              </Text>
            </View>
          )}
        </View>
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
        className="bg-canvas-subtle border border-border-default rounded-md py-2.5 px-3 flex-row items-center gap-3"
        style={shadow.paper}
      >
        <Identity name={hero.name} level={hero.level} canLevelUp={hero.canLevelUp} />
        <Meter label="HP"  value={hero.hp}  max={hero.hpMax}  tone="hp" />
        <Meter label="MP"  value={hero.mp}  max={hero.mpMax}  tone="mp" />
        <Meter label="EXP" value={hero.exp} max={hero.expMax} tone="exp" />
        <View style={{ position: 'absolute', top: 4, right: 6 }}>
          <Text style={{ fontSize: 9, color: colors.fg.subtle }}>
            {expanded ? '▴' : '▾'}
          </Text>
        </View>
      </Pressable>

      {expanded && <HeroDetail hero={hero} />}
    </View>
  );
}
