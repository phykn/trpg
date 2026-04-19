import { Text, Pressable } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Theme, typeStyle } from '@/constants/theme';

export function DiceButton({ enabled, rolling, onPress }: {
  enabled: boolean; rolling: boolean; onPress: () => void;
}) {
  const active = enabled && !rolling;
  const disabled = !enabled || rolling;
  return (
    <Pressable onPress={onPress} disabled={disabled} style={{
      flexDirection: 'row', alignItems: 'center', gap: 6,
      height: 32, paddingHorizontal: Theme.space.md, borderRadius: Theme.radius.pill,
      backgroundColor: active ? Theme.accentSoft : 'transparent',
      borderWidth: 1, borderColor: active ? Theme.accent : Theme.border,
      opacity: disabled ? 0.55 : 1,
    }}>
      <Svg width={15} height={15} viewBox="0 0 24 24" fill="none">
        <Path d="M12 2.5L20.5 7.5V16.5L12 21.5L3.5 16.5V7.5L12 2.5Z"
          stroke={active ? Theme.accent : Theme.textFaint} strokeWidth={1.6} strokeLinejoin="round" />
        <Path d="M12 2.5L12 21.5M3.5 7.5L20.5 16.5M20.5 7.5L3.5 16.5"
          stroke={active ? Theme.accent : Theme.textFaint} strokeWidth={0.8} opacity={0.5} />
      </Svg>
      <Text style={{
        color: active ? Theme.accent : Theme.textFaint,
        fontFamily: enabled ? Theme.fonts.sansSemibold : Theme.fonts.sansMedium,
        ...typeStyle('caption', { fontWeight: (enabled ? '600' : '500') as '600' | '500' }),
      }}>{enabled ? '굴리기' : '주사위'}</Text>
    </Pressable>
  );
}
