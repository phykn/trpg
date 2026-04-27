import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { useGame } from '@/hooks/useGame';

import { NewGame } from './new-game';
import { Playing } from './Playing';

export function Shell() {
  const game = useGame();

  if (game.status === 'loading') {
    return (
      <View className="flex-1 bg-canvas-default items-center justify-center gap-3">
        <ActivityIndicator color={colors.accent.fg} />
        <Text
          className="font-sans-semibold text-meta text-fg-subtle"
          style={{ letterSpacing: 1.2 }}
        >
          불러오는 중
        </Text>
      </View>
    );
  }

  if (game.status === 'error') {
    return (
      <View className="flex-1 bg-canvas-default items-center justify-center px-5 gap-2">
        <View className="items-center gap-1">
          <Text
            className="font-sans-semibold text-meta text-danger-fg"
            style={{ letterSpacing: 1.2 }}
          >
            오류
          </Text>
          <Text className="font-sans text-body text-fg-default text-center">
            {game.errorMessage ?? '알 수 없는 오류'}
          </Text>
        </View>
        <Pressable
          onPress={game.refresh}
          className="px-4 h-9 mt-2 rounded-md bg-canvas-inset border border-border-default items-center justify-center active:bg-border-default"
        >
          <Text className="font-sans-medium text-body text-fg-default">다시 시도</Text>
        </Pressable>
      </View>
    );
  }

  if (game.status === 'no-game') {
    return <NewGame onSubmit={game.startNewGame} />;
  }

  return <Playing game={game} />;
}
