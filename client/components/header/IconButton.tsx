import { Pressable } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/design/tokens';

export const ICON_PATH = {
  menu: 'M5 7h14M5 12h14M5 17h14',
  volumeOn: 'M11 5L6 9H2v6h4l5 4V5z M15.54 8.46a5 5 0 0 1 0 7.07 M19.07 4.93a10 10 0 0 1 0 14.14',
  volumeOff: 'M11 5L6 9H2v6h4l5 4V5z M22 9l-6 6 M16 9l6 6',
  map: 'M9 3L3 6v15l6-3 6 3 6-3V3l-6 3-6-3z M9 3v15 M15 6v15',
} as const;

export function IconButton({ d, label, onPress }: { d: string; label: string; onPress?: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      className="w-8 h-8 rounded-sm items-center justify-center shrink-0 active:bg-canvas-inset"
    >
      <Svg width={18} height={18} viewBox="0 0 24 24" fill="none"
        stroke={colors.fg.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
        <Path d={d} />
      </Svg>
    </Pressable>
  );
}
