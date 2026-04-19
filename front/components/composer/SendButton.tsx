import { Pressable } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { Theme } from '@/constants/theme';

export function SendButton({ enabled, onPress }: {
  enabled: boolean; onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} disabled={!enabled} style={{
      width: 34, height: 34, borderRadius: Theme.radius.pill,
      backgroundColor: enabled ? Theme.accent : Theme.bgElev,
      alignItems: 'center', justifyContent: 'center',
    }}>
      <Svg width={15} height={15} viewBox="0 0 24 24" fill="none">
        <Path d="M12 19V5M5 12l7-7 7 7"
          stroke={enabled ? Theme.bgCard : Theme.textFaint}
          strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    </Pressable>
  );
}
