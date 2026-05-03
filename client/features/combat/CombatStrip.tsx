import { Animated, Text, View } from 'react-native';

import { Bar, Surface, useEntryAnimation } from '@/components/ui';
import { colors, toneColor } from '@/design/tokens';

import type { CombatBadge } from './types';

export function CombatStrip({ combat }: { combat: CombatBadge }) {
  const { scale, opacity } = useEntryAnimation();
  return (
    <Animated.View
      className="mx-5 mt-1"
      style={{ transform: [{ scale }], opacity }}
    >
      <Surface
        stripeColor={colors.danger.fg}
        className="px-4 py-3 gap-2"
      >
        <View className="flex-row items-center gap-2">
          <Text
            className="font-sans-bold text-caption text-danger-fg uppercase"
            style={{ letterSpacing: 1.2 }}
          >
            전투
          </Text>
          <Text className="font-mono text-caption text-fg-subtle">·</Text>
          <Text
            className="font-mono text-caption text-fg-muted"
            style={{ fontVariant: ['tabular-nums'] }}
          >
            R{combat.round}
          </Text>
          <Text className="font-mono text-caption text-fg-subtle">·</Text>
          <Text
            className="font-sans-medium text-caption text-fg-default flex-1"
            numberOfLines={1}
          >
            {combat.turnLabel}
          </Text>
        </View>
        {combat.enemies.length > 0 && (
          <View className="gap-1">
            {combat.enemies.map((e, i) => (
              <View key={`${e.name}-${i}`} className="flex-row items-center gap-2">
                <Text
                  numberOfLines={1}
                  className={`font-sans-medium text-caption ${e.alive ? 'text-fg-default' : 'text-fg-subtle line-through'}`}
                  style={{ maxWidth: 120, flexShrink: 1 }}
                >
                  {e.name}
                </Text>
                <View className="flex-1">
                  <Bar value={e.hp} max={e.hpMax} color={toneColor.hp} h={4} />
                </View>
                <Text
                  className="font-mono text-caption text-fg-muted"
                  style={{ fontVariant: ['tabular-nums'], minWidth: 44, textAlign: 'right' }}
                >
                  {e.hp}/{e.hpMax}
                </Text>
              </View>
            ))}
          </View>
        )}
      </Surface>
    </Animated.View>
  );
}
