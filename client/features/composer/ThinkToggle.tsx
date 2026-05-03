import { Pressable, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors } from '@/design/tokens';

export function ThinkToggle({ think, onToggle, disabled = false }: {
  think: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  const label = think ? '정확하게' : '빠르게';
  const bgClass = think ? 'bg-accent-muted' : 'bg-canvas-inset';
  const stateClass = disabled ? 'opacity-50' : 'active:opacity-80';
  return (
    <Pressable
      onPress={disabled ? undefined : onToggle}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected: think }}
      className={`flex-row items-center justify-center h-8 px-3 rounded-full ${stateClass} ${bgClass}`}
    >
      {!think && (
        <View className="mr-1">
          <Svg width={12} height={12} viewBox="0 0 24 24" fill={colors.fg.default}>
            <Path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
          </Svg>
        </View>
      )}
      <Text className="font-sans text-panel text-fg-default">{label}</Text>
    </Pressable>
  );
}
