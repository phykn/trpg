import { Pressable } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/design/tokens';

export function SendButton({ enabled, onPress }: {
  enabled: boolean;
  onPress: () => void;
}) {
  const bgClass = enabled ? 'bg-accent-fg' : 'bg-canvas-inset';
  const stroke = enabled ? colors.canvas.subtle : colors.fg.subtle;

  return (
    <Pressable
      onPress={onPress}
      disabled={!enabled}
      accessibilityRole="button"
      accessibilityLabel="행동 보내기"
      accessibilityState={{ disabled: !enabled }}
      testID="send-button"
      className={`items-center justify-center h-8 px-3 rounded-full ${bgClass} ${enabled ? 'active:opacity-80' : ''}`}
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
    </Pressable>
  );
}
