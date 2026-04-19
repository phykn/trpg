import React from 'react';
import { View, Text, Pressable } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/design/tokens';

const HINT_DURATION = 1400;

export function DiceButton({ enabled, rolling, onPress }: {
  enabled: boolean;
  rolling: boolean;
  onPress: () => void;
}) {
  const active = enabled && !rolling;
  const disabled = !enabled || rolling;
  const [hint, setHint] = React.useState(false);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const handlePress = () => {
    if (disabled) {
      setHint(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setHint(false), HINT_DURATION);
      return;
    }
    onPress();
  };

  const strokeColor = active ? colors.accent.fg : colors.fg.subtle;
  const bgClass = active ? 'bg-accent-muted border-accent-fg' : 'bg-transparent border-border-default';
  const textClass = active ? 'text-accent-fg' : 'text-fg-subtle';
  const fontClass = enabled ? 'font-sans-semibold' : 'font-sans-medium';

  return (
    <View>
      {hint && (
        <View
          className="absolute items-center z-10"
          style={{ bottom: 38, left: -120, right: -120 }}
        >
          <View className="bg-fg-default px-2.5 py-1 rounded-sm">
            <Text className="font-sans-medium text-caption text-fg-on-emphasis">
              아직은 때가 아닙니다.
            </Text>
          </View>
        </View>
      )}
      <Pressable
        onPress={handlePress}
        className={`flex-row items-center gap-1.5 h-8 px-3 rounded-full border ${bgClass}`}
        style={{ opacity: disabled ? 0.55 : 1 }}
      >
        <Svg width={15} height={15} viewBox="0 0 24 24" fill="none">
          <Path
            d="M12 2.5L20.5 7.5V16.5L12 21.5L3.5 16.5V7.5L12 2.5Z"
            stroke={strokeColor} strokeWidth={1.6} strokeLinejoin="round"
          />
          <Path
            d="M12 2.5L12 21.5M3.5 7.5L20.5 16.5M20.5 7.5L3.5 16.5"
            stroke={strokeColor} strokeWidth={0.8} opacity={0.5}
          />
        </Svg>
        <Text className={`text-caption ${fontClass} ${textClass}`}>
          {enabled ? '굴리기' : '주사위'}
        </Text>
      </Pressable>
    </View>
  );
}
