import { Text } from 'react-native';

const TONES = { gold: 'text-gold-fg', danger: 'text-danger-fg', muted: 'text-fg-muted' };

export function Boxes({ value, boxes, tone = 'gold' }: { value: number; boxes: number; tone?: keyof typeof TONES }) {
  return (
    <Text accessibilityLabel={`${value}/${boxes}`} className={`font-mono text-caption ${TONES[tone]}`}>
      {'■'.repeat(Math.min(value, boxes))}{'□'.repeat(Math.max(0, boxes - value))}
      <Text className="text-fg-subtle"> {value}/{boxes}</Text>
    </Text>
  );
}
