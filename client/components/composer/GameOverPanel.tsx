import { Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';

type Props = { onRestart: () => void };

export function GameOverPanel({ onRestart }: Props) {
  return (
    <View className="px-4 py-6 items-center gap-4">
      <Text className="font-sans text-body text-fg-muted">{ko.gameOver.ending}</Text>
      <Pressable
        className="px-6 py-3 rounded-md bg-accent-fg active:opacity-80"
        onPress={onRestart}
        accessibilityRole="button"
        accessibilityLabel={ko.gameOver.restartAction}
      >
        <Text className="font-sans-semibold text-title text-fg-on-emphasis">{ko.gameOver.restart}</Text>
      </Pressable>
    </View>
  );
}
