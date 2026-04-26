import { Pressable } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/design/tokens';

export function MenuButton({ onPress }: { onPress?: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="w-8 h-8 rounded-sm items-center justify-center shrink-0"
    >
      <Svg width={18} height={18} viewBox="0 0 24 24" fill="none"
        stroke={colors.fg.muted} strokeWidth={1.8} strokeLinecap="round">
        <Path d="M5 7h14M5 12h14M5 17h14" />
      </Svg>
    </Pressable>
  );
}
