import { View, Text } from 'react-native';
import { colors } from '@/design/tokens';
import { InlineNodes } from '@/components/ui';
import type { LogEntry } from '@/types/ui';

type RollEntry = Extract<LogEntry, { kind: 'roll' }>;

export function RollResult({ entry }: { entry: RollEntry }) {
  const pass = entry.result === 'success';
  const accent = pass ? colors.success.fg : colors.danger.fg;
  const total = entry.roll + entry.mod;
  const modStr = entry.mod >= 0 ? `+${entry.mod}` : `${entry.mod}`;
  const colorClass = pass ? 'text-success-fg' : 'text-danger-fg';

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
    <View
      className="flex-row items-center bg-canvas-subtle border border-border-default rounded-md py-2 px-3 gap-3"
      style={{
        minHeight: 32,
        borderLeftWidth: 3,
        borderLeftColor: accent,
      }}
    >
      <Text
        className={`font-sans-bold text-panel uppercase shrink-0 ${colorClass}`}
        style={{ letterSpacing: 1.2 }}
      >
        {pass ? '성공' : '실패'}
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
  );
}
