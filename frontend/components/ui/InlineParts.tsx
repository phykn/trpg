import { View, Text } from 'react-native';
import { colors, toneColor } from '@/design/tokens';
import { Row } from './Row';
import type { DisplayPart } from '@/types/ui';

export function InlineParts({ label, parts }: { label: string; parts: DisplayPart[] }) {
  return (
    <Row label={label} labelAlign="right" gap="lg">
      <View className="flex-1 min-w-0 flex-row items-center gap-3">
        {parts.map((p, i) => {
          const color = p.tone ? toneColor[p.tone] : colors.fg.default;
          return (
            <View key={i} className="flex-1 min-w-0 flex-row items-center gap-1">
              {p.label && (
                <Text
                  className="font-mono-semibold text-panel text-fg-subtle uppercase"
                  style={{ letterSpacing: 1.2 }}
                >
                  {p.label}
                </Text>
              )}
              <Text
                numberOfLines={1}
                className="font-mono-semibold text-panel flex-1 min-w-0"
                style={{ color, fontVariant: ['tabular-nums'] }}
              >
                {p.text}
              </Text>
            </View>
          );
        })}
      </View>
    </Row>
  );
}
