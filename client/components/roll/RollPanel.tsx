import { Animated, Pressable, Text, View } from 'react-native';

import { Surface, useEntryAnimation } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { buildDiceCells } from '@/logic/roll/panel';
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
  const cells = buildDiceCells(roll.requiredRoll);

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

          <View className="flex-row gap-0.5">
            {cells.map((cell) => (
              <View
                key={cell.value}
                className="h-7 flex-1 items-center justify-center rounded-sm"
                style={{
                  backgroundColor:
                    cell.band === 'success'
                      ? `${colors.success.fg}${cell.selected ? '55' : '24'}`
                      : `${colors.danger.fg}${cell.selected ? '66' : '24'}`,
                  borderColor: cell.selected ? colors.accent.fg : 'transparent',
                  borderWidth: cell.selected ? 1 : 0,
                }}
              >
                <Text
                  className="font-mono-semibold text-caption"
                  style={{ color: cell.selected ? colors.fg.default : colors.fg.muted }}
                >
                  {cell.value}
                </Text>
              </View>
            ))}
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
