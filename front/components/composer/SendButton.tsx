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
      className={`w-9 h-9 rounded-full items-center justify-center ${bgClass}`}
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
