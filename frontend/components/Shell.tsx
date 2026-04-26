import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { useGame } from '@/hooks/useGame';

import { NewGame } from './NewGame';
import { Playing } from './Playing';

export function Shell() {
  const game = useGame();

  if (game.status === 'loading') {
    return (
      <View className="flex-1 bg-canvas-default items-center justify-center">
        <ActivityIndicator color={colors.accent.fg} />
      </View>
    );
  }

  if (game.status === 'error') {
    return (
      <View className="flex-1 bg-canvas-default items-center justify-center px-5 gap-3">
        <Text className="font-sans text-body text-danger-fg text-center">
          {game.errorMessage ?? '알 수 없는 오류'}
        </Text>
        <Pressable
          onPress={game.refresh}
          className="px-4 h-9 rounded-md bg-canvas-inset border border-border-default items-center justify-center"
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
