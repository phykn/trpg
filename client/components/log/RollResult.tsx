import { Animated, Text, View } from 'react-native';

import { Glyph } from '@/components/ui';
import { colors, shadow } from '@/design/tokens';
import { useEntryAnimation } from '@/hooks/useEntryAnimation';
import type { LogEntry } from '@/types/ui';

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

export function RollResult({ entry }: { entry: RollEntry }) {
  const tone = TONE[entry.result];
  const margin = marginText(entry);
  const { scale, opacity } = useEntryAnimation();

  return (
    <Animated.View style={{ transform: [{ scale }], opacity }}>
      <View
        className="bg-canvas-subtle border border-border-default rounded-md px-3 py-2.5"
        style={{ borderLeftWidth: 2, borderLeftColor: tone.color, ...shadow.paper }}
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
      </View>
    </Animated.View>
  );
}
