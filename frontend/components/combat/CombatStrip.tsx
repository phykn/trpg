import { Text, View } from 'react-native';

import type { CombatBadge } from '@/types/domain';

export function CombatStrip({ combat }: { combat: CombatBadge }) {
  return (
    <View className="mx-5 mt-1 px-3 py-1.5 rounded-md bg-canvas-inset border border-danger-fg/40 flex-row items-center gap-3">
      <Text className="font-sans-medium text-caption text-danger-fg">전투</Text>
      <Text className="font-sans text-caption text-fg-muted">R{combat.round}</Text>
      <View className="w-px h-3 bg-border-default" />
      <Text className="font-sans-medium text-caption text-fg-default">{combat.turnLabel}</Text>
      {combat.enemies.length > 0 ? (
        <>
          <View className="w-px h-3 bg-border-default" />
          <View className="flex-1 flex-row flex-wrap gap-x-3 gap-y-0.5">
            {combat.enemies.map((e, i) => (
              <Text
                key={`${e.name}-${i}`}
                className={`font-sans text-caption ${e.alive ? 'text-fg-muted' : 'text-fg-subtle line-through'}`}
              >
                {e.name} {e.hp}/{e.hpMax}
              </Text>
            ))}
          </View>
        </>
      ) : null}
    </View>
  );
}
