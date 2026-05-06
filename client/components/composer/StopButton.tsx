import { Pressable, View } from 'react-native';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';

export function StopButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={ko.composer.stopAction}
      testID="stop-button"
      className="items-center justify-center h-8 px-3 rounded-full bg-accent-fg active:opacity-80"
    >
      <View style={{ width: 11, height: 11, borderRadius: 2, backgroundColor: colors['fg']['on-emphasis'] }} />
    </Pressable>
  );
}
