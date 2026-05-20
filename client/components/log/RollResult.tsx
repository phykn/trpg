import { Animated, Text, View } from 'react-native';

import { signed, useEntryAnimation } from '@/components/ui';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';

import type { LogEntry } from '@/logic/log/types';

type RollEntry = Extract<LogEntry, { kind: 'roll' }>;

const TONE = {
  success: { color: colors.success.fg, label: ko.roll.success, cls: 'text-success-fg' },
  fail:    { color: colors.danger.fg,  label: ko.roll.fail,    cls: 'text-danger-fg'  },
} as const;

function marginText(entry: RollEntry): string | null {
  if (entry.roll === 20 || entry.roll === 1) return null;
  if (entry.margin > 0) return `+${entry.margin} ${ko.roll.exceed}`;
  if (entry.margin < 0) return `${-entry.margin} ${ko.roll.short}`;
  return null;
}

export function RollResult({ entry }: { entry: RollEntry }) {
  const tone = TONE[entry.result];
  const margin = marginText(entry);
  const { scale, opacity } = useEntryAnimation();
  // breakdown[0] is always the d20 roll itself; slice(1) sums only ability/affinity bonuses.
  const breakdown = entry.bonus_breakdown ?? [];
  const totalBonus = breakdown.slice(1).reduce((acc, item) => acc + item.value, 0);

  return (
    <Animated.View style={{ transform: [{ scale }], opacity }}>
      <View
        className="flex-row items-center"
        style={{
          gap: 8,
        }}
      >
        <Text
          className={`font-sans-bold text-caption ${tone.cls}`}
        >
          {tone.label}
        </Text>
        <Text
          className="font-sans-semibold text-caption text-fg-muted flex-1"
          numberOfLines={1}
        >
          {entry.check}
        </Text>
        <Text
          className="font-mono-semibold text-caption text-fg-default"
          style={{ fontVariant: ['tabular-nums'] }}
        >
          d20 {entry.roll}
        </Text>
        {totalBonus !== 0 && (
          <Text
            className="font-mono text-caption text-fg-muted"
            style={{ fontVariant: ['tabular-nums'] }}
          >
            ({signed(totalBonus)})
          </Text>
        )}
        {margin !== null && (
          <Text
            className={`font-sans-medium text-caption ${tone.cls}`}
            style={{ fontVariant: ['tabular-nums'] }}
          >
            {margin}
          </Text>
        )}
      </View>
    </Animated.View>
  );
}
