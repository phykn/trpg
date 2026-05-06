import { Animated, Text, View } from 'react-native';

import { Glyph, Surface, useEntryAnimation } from '@/components/ui';
import { colors } from '@/design/tokens';

import type { LogEntry } from '@/logic/log/types';

type RollEntry = Extract<LogEntry, { kind: 'roll' }>;

const TONE = {
  success: { color: colors.success.fg, label: '성공', cls: 'text-success-fg' },
  partial: { color: colors.exp.fg,     label: '절반', cls: 'text-exp-fg'     },
  fail:    { color: colors.danger.fg,  label: '실패', cls: 'text-danger-fg'  },
} as const;

function marginText(entry: RollEntry): string | null {
  if (entry.roll === 20 || entry.roll === 1) return null;
  if (entry.margin > 0) return `+${entry.margin} 초과`;
  if (entry.margin < 0) return `${-entry.margin} 부족`;
  return null;
}

const signed = (n: number) => (n >= 0 ? `+${n}` : `${n}`);

export function RollResult({ entry }: { entry: RollEntry }) {
  const tone = TONE[entry.result];
  const margin = marginText(entry);
  const { scale, opacity } = useEntryAnimation();
  // breakdown[0] is always the d20 roll itself; slice(1) sums only ability/affinity bonuses.
  const breakdown = entry.bonus_breakdown ?? [];
  const totalBonus = breakdown.slice(1).reduce((acc, item) => acc + item.value, 0);

  return (
    <Animated.View style={{ transform: [{ scale }], opacity }}>
      <Surface
        stripeColor={tone.color}
        className="px-3 py-2.5"
      >
        <View className="flex-row items-center" style={{ gap: 8 }}>
          <View
            className="px-2 py-0.5 rounded-full flex-row items-center"
            style={{ backgroundColor: `${tone.color}26`, gap: 5 }}
          >
            <Glyph kind="filled" color={tone.color} size={8} />
            <Text
              className={`font-sans-bold text-caption uppercase ${tone.cls}`}
              style={{ letterSpacing: 1.2 }}
            >
              {tone.label}
            </Text>
          </View>
          <Text
            className="font-sans-semibold text-panel text-fg-subtle"
            style={{ letterSpacing: 1.2 }}
            numberOfLines={1}
          >
            {entry.check}
          </Text>
          <Text className="font-mono text-panel text-fg-subtle">·</Text>
          <Text
            className="font-sans-semibold text-panel text-fg-subtle"
            style={{ letterSpacing: 1.2 }}
          >
            주사위
          </Text>
          <Text
            className="font-mono-semibold text-panel text-fg-default"
            style={{ fontVariant: ['tabular-nums'] }}
          >
            {entry.roll}
          </Text>
          {totalBonus !== 0 && (
            <Text
              className="font-mono text-panel text-fg-muted"
              style={{ fontVariant: ['tabular-nums'] }}
            >
              ({signed(totalBonus)})
            </Text>
          )}
          <View style={{ flex: 1 }} />
          {margin !== null && (
            <Text
              className={`font-sans-medium text-caption ${tone.cls}`}
              style={{ fontVariant: ['tabular-nums'] }}
            >
              {margin}
            </Text>
          )}
        </View>
      </Surface>
    </Animated.View>
  );
}
