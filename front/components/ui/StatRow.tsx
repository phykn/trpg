import { Text } from 'react-native';
import { toneColor } from '@/design/tokens';
import { Bar } from './Bar';
import { Row } from './Row';
import type { BarDef } from '@/types/ui';

export function StatRow({ label, value, max, tone, display, signed }: BarDef) {
  const color = toneColor[tone];
  return (
    <Row
      label={label}
      trailing={
        <Text
          className="font-mono-semibold text-panel text-fg-default"
          style={{ fontVariant: ['tabular-nums'] }}
        >
          {display}
        </Text>
      }
    >
      <Bar value={value} max={max} color={color} signed={signed} />
    </Row>
  );
}
