import { Text } from 'react-native';

import { colors } from '@/design/tokens';

const CHAR = {
  filled: '◆',
  outline: '◇',
} as const;

const TONE = {
  accent: colors.accent.fg,
  subtle: colors.fg.subtle,
  muted: colors.fg.muted,
} as const;

export function Glyph({
  kind = 'outline',
  tone = 'accent',
  size = 12,
  color,
  style,
}: {
  kind?: keyof typeof CHAR;
  tone?: keyof typeof TONE;
  size?: number;
  color?: string;
  style?: React.ComponentProps<typeof Text>['style'];
}) {
  return (
    <Text
      style={[
        { color: color ?? TONE[tone], fontSize: size, lineHeight: size * 1.1 },
        style,
      ]}
      accessibilityElementsHidden
      importantForAccessibility="no"
    >
      {CHAR[kind]}
    </Text>
  );
}
