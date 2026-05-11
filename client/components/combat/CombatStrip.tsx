import { Animated, Pressable, Text, View } from 'react-native';

import { Surface, useEntryAnimation } from '@/components/ui';
import { compose, ko } from '@/locale/ko';

import { buildCombatActions } from '@/logic/combat/actions';
import type { CombatBadge } from '@/logic/combat/types';
import type { PanelAction } from '@/logic/info-panel';

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
    <View className="mx-5 mt-1">
      <Animated.View style={{ transform: [{ scale }], opacity }}>
        <Surface className="px-4 py-3 gap-2.5">
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
                {combat.turnLabel} · R{combat.round}
              </Text>
            </View>
            {target ? (
              <View className="items-end gap-1">
                <Text className="font-sans-semibold text-caption text-fg-default">
                  내 하트 {combat.playerHearts.current}/{combat.playerHearts.maximum}
                </Text>
                <Text className="font-sans-semibold text-caption text-fg-default">
                  적 하트 {combat.enemyHearts.current}/{combat.enemyHearts.maximum}
                </Text>
              </View>
            ) : null}
          </View>
          {actions.length > 0 && onAction ? (
            <View className="flex-row gap-2">
              {actions.map((action) => (
                <Pressable
                  key={`${action.kind}:${action.label}`}
                  onPress={() => onAction(action)}
                  disabled={actionDisabled}
                  accessibilityRole="button"
                  accessibilityLabel={action.label}
                  className={`h-9 flex-1 items-center justify-center rounded-md border border-border-default ${actionDisabled ? 'bg-canvas-inset opacity-60' : 'bg-canvas-inset active:opacity-80'}`}
                >
                  <Text className="font-sans-semibold text-panel text-fg-default">
                    {actionDisabled ? ko.status.busy : action.label}
                  </Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </Surface>
      </Animated.View>
    </View>
  );
}
