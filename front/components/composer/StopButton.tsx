import { Pressable, View } from 'react-native';
import { colors } from '@/design/tokens';

export function StopButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="items-center justify-center h-8 px-3 rounded-full bg-accent-fg"
    >
      <View style={{ width: 11, height: 11, borderRadius: 2, backgroundColor: colors.canvas.subtle }} />
    </Pressable>
  );
}
