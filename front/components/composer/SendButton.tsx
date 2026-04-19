import { Pressable, Text } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/design/tokens';

export function SendButton({ enabled, onPress }: {
  enabled: boolean;
  onPress: () => void;
}) {
  const bgClass = enabled ? 'bg-accent-fg' : 'bg-canvas-inset';
  const stroke = enabled ? colors.canvas.subtle : colors.fg.subtle;
  const textClass = enabled ? 'text-fg-on-emphasis' : 'text-fg-subtle';

  return (
    <Pressable
      onPress={onPress}
      disabled={!enabled}
      className={`flex-row items-center gap-1.5 h-8 px-3 rounded-full ${bgClass}`}
    >
      <Svg width={15} height={15} viewBox="0 0 24 24" fill="none">
        <Path
          d="M12 19V5M5 12l7-7 7 7"
          stroke={stroke}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </Svg>
      <Text className={`text-caption font-sans-semibold ${textClass}`}>
        전송
      </Text>
    </Pressable>
  );
}
