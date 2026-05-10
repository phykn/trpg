import { Pressable, Text } from 'react-native';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';

export function SendButton({ enabled, onPress }: {
  enabled: boolean;
  onPress: () => void;
}) {
  const bgClass = enabled ? 'bg-accent-fg' : 'bg-canvas-inset';
  const stroke = enabled ? colors['fg']['on-emphasis'] : colors.fg.subtle;

  return (
    <Pressable
      onPress={onPress}
      disabled={!enabled}
      accessibilityRole="button"
      accessibilityLabel={ko.composer.sendAction}
      accessibilityState={{ disabled: !enabled }}
      testID="send-button"
      className={`items-center justify-center h-10 px-3 rounded-md ${bgClass} ${enabled ? 'active:opacity-80' : ''}`}
      style={{ minWidth: 48 }}
    >
      <Text className="font-sans-semibold text-panel" style={{ color: stroke }}>
        {ko.composer.send}
      </Text>
    </Pressable>
  );
}
