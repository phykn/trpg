import { Animated, Pressable, Text, View } from 'react-native';

import { Surface, useEntryAnimation } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { PendingRoll } from '@/logic/roll/types';

export function RollPanel({
  roll,
  onRoll,
  disabled = false,
}: {
  roll: PendingRoll;
  onRoll: (rollId: string) => void;
  disabled?: boolean;
}) {
  const { scale, opacity } = useEntryAnimation();

  return (
    <View className="mx-5 mt-1">
      <Animated.View style={{ transform: [{ scale }], opacity }}>
        <Surface className="px-4 py-3 gap-2">
          <View className="flex-row items-center justify-between gap-3">
            <Text className="font-sans-bold text-title text-fg-default flex-1" numberOfLines={1}>
              {roll.title}
            </Text>
            <Text
              className="font-mono-semibold text-title text-accent-fg"
              style={{ fontVariant: ['tabular-nums'] }}
            >
              {roll.requiredRoll} {ko.roll.orMore}
            </Text>
          </View>

          <Pressable
            onPress={() => onRoll(roll.id)}
            disabled={disabled}
            accessibilityRole="button"
            accessibilityLabel={ko.roll.rollLabel}
            className={`h-10 items-center justify-center rounded-sm bg-accent-fg ${disabled ? 'opacity-60' : 'active:opacity-80'}`}
          >
            <Text className="font-sans-semibold text-panel text-fg-on-emphasis">
              {ko.action.roll}
            </Text>
          </Pressable>
        </Surface>
      </Animated.View>
    </View>
  );
}
