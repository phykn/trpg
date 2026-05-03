import { Pressable, Text, View } from 'react-native';

type Props = { onRestart: () => void };

export function GameOverPanel({ onRestart }: Props) {
  return (
    <View className="px-4 py-6 items-center gap-4">
      <Text className="font-sans text-body text-fg-muted">이야기는 여기서 끝납니다.</Text>
      <Pressable
        className="px-6 py-3 rounded-md bg-accent-fg active:opacity-80"
        onPress={onRestart}
        accessibilityRole="button"
        accessibilityLabel="새 이야기 시작"
      >
        <Text className="font-sans-semibold text-title text-fg-on-emphasis">새 이야기 시작</Text>
      </Pressable>
    </View>
  );
}
