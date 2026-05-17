import { Animated, Pressable, Text, View } from 'react-native';

import { useEntryAnimation } from '@/components/ui';
import { compose, ko } from '@/locale/ko';

import { buildCombatActions } from '@/logic/combat/actions';
import type { CombatBadge, CombatHeart } from '@/logic/combat/types';
import type { PanelAction } from '@/logic/info-panel';

function HeartDots({ heart }: { heart: CombatHeart }) {
  return (
    <View className="flex-row gap-1">
      {Array.from({ length: heart.maximum }).map((_, index) => (
        <View
          key={index}
          className={`h-2.5 w-2.5 rounded-full ${index < heart.current ? 'bg-accent-fg' : 'bg-canvas-floating'}`}
        />
      ))}
    </View>
  );
}

export function CombatStrip({
  combat,
  onAction,
  actionDisabled = false,
}: {
  combat: CombatBadge;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
}) {
  const { scale, opacity } = useEntryAnimation();
  const actions = buildCombatActions(combat);
  const target = combat.enemies.find((enemy) => enemy.alive) ?? combat.enemies[0] ?? null;
  return (
    <View className="mt-1 border-t border-border-default bg-canvas-default px-5 pt-2.5 pb-3">
      <Animated.View style={{ transform: [{ scale }], opacity }}>
        <View className="gap-3">
          <View className="flex-row items-start gap-3">
            <View className="flex-1 min-w-0">
              <Text
                className="font-sans-bold text-title text-fg-default"
                numberOfLines={1}
              >
                {target ? compose.combatWith(target.name) : ko.combat.label}
              </Text>
              <Text
                className="font-sans-medium text-caption text-fg-muted"
                numberOfLines={1}
                style={{ fontVariant: ['tabular-nums'] }}
              >
                {compose.combatExchange(combat.round)} · {combat.turnLabel}
              </Text>
            </View>
            {target ? (
              <View className="min-w-24 gap-1">
                <View className="flex-row items-center justify-between gap-2">
                  <Text className="font-sans text-caption text-fg-muted flex-1" numberOfLines={1}>
                    {ko.combat.player}
                  </Text>
                  <HeartDots heart={combat.playerHearts} />
                </View>
                <View className="flex-row items-center justify-between gap-2">
                  <Text className="font-sans text-caption text-fg-muted flex-1" numberOfLines={1}>
                    {target.name}
                  </Text>
                  <HeartDots heart={combat.enemyHearts} />
                </View>
              </View>
            ) : null}
          </View>
          {actions.length > 0 && onAction ? (
            <View className="flex-row gap-2">
              {actions.map((action, index) => {
                const primary = index === 0;
                return (
                <Pressable
                  key={`${action.kind}:${action.label}`}
                  onPress={() => onAction(action)}
                  disabled={actionDisabled}
                  accessibilityRole="button"
                  accessibilityLabel={action.label}
                  className={`h-10 flex-1 items-center justify-center rounded-sm border ${primary ? 'border-accent-fg bg-accent-fg' : 'border-border-default bg-canvas-inset'} ${actionDisabled ? 'opacity-60' : 'active:opacity-80'}`}
                >
                  <Text className={`font-sans-semibold text-panel ${primary ? 'text-fg-on-emphasis' : 'text-fg-default'}`} numberOfLines={1}>
                    {action.label}
                  </Text>
                </Pressable>
              );
              })}
            </View>
          ) : null}
        </View>
      </Animated.View>
    </View>
  );
}
