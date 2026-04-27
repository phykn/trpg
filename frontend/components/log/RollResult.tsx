import React from 'react';
import { Animated, Easing, View, Text } from 'react-native';
import { colors } from '@/design/tokens';
import { InlineNodes } from '@/components/ui';
import type { LogEntry } from '@/types/ui';

type RollEntry = Extract<LogEntry, { kind: 'roll' }>;

const TONE = {
  success: { color: colors.success.fg, label: '성공', cls: 'text-success-fg' },
  partial: { color: colors.exp.fg,     label: '절반', cls: 'text-exp-fg'     },
  fail:    { color: colors.danger.fg,  label: '실패', cls: 'text-danger-fg'  },
} as const;

export function RollResult({ entry }: { entry: RollEntry }) {
  const tone = TONE[entry.result];
  const total = entry.roll + entry.mod;
  const modStr = entry.mod >= 0 ? `+${entry.mod}` : `${entry.mod}`;

  const scale = React.useRef(new Animated.Value(1.04)).current;
  const opacity = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    Animated.parallel([
      Animated.timing(scale, {
        toValue: 1,
        duration: 220,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 220,
        useNativeDriver: true,
      }),
    ]).start();
  }, [scale, opacity]);

  const resultValue = (
    <Text
      numberOfLines={1}
      className="font-mono-semibold text-panel"
      style={{ fontVariant: ['tabular-nums'] }}
    >
      <Text className="text-fg-default">{total}</Text>
      <Text className="text-fg-subtle"> ({entry.roll}{modStr})</Text>
    </Text>
  );

  return (
    <Animated.View style={{ transform: [{ scale }], opacity }}>
      <View
        className="flex-row items-center bg-canvas-subtle border border-border-default rounded-md py-2 px-3 gap-3"
        style={{
          minHeight: 32,
          borderLeftWidth: 3,
          borderLeftColor: tone.color,
        }}
      >
        <Text
          className={`font-sans-bold text-panel uppercase shrink-0 ${tone.cls}`}
          style={{ letterSpacing: 1.2 }}
        >
          {tone.label}
        </Text>
        <View className="h-3.5 bg-border-default" style={{ width: 1 }} />
        <InlineNodes
          entries={[
            ['판정', entry.check],
            ['난이도', entry.dc],
            ['결과', resultValue],
          ]}
          weights={[1, 1, 2]}
        />
      </View>
    </Animated.View>
  );
}
