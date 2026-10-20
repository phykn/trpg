import Head from 'expo-router/head';
import { ActivityIndicator, Text, View } from 'react-native';
import { useReducedMotion } from 'react-native-reanimated';

import { Button } from '@/components/ui/Button';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { useGame } from '@/logic/useGame';
import { useViewportHeight } from '@/logic/useViewportHeight';
import { Play } from '@/screens/Play';
import { Start } from '@/screens/Start';

export default function Index() {
  const height = useViewportHeight();
  const game = useGame(useReducedMotion());
  const starting = game.phase === 'start' || (game.phase === 'sending' && !game.view);
  return (
    <View className="items-center bg-canvas-inset" style={{ height }}>
      <Head><title>{ko.brand}</title></Head>
      <View className="mobile-frame min-h-0 w-full max-w-mobile flex-1 border-x border-border-default bg-canvas-default">
        {game.phase === 'blocked' ? (
          <View className="flex-1 items-center justify-center gap-5 px-5">
            <Text className="text-center font-sans text-body text-fg-muted">{ko.blocked}</Text>
            <Button icon="home" label={ko.toTitle} onPress={game.newGame} />
          </View>
        ) : starting ? (
          <Start stories={game.stories} busy={game.phase === 'sending'} onCreate={game.create}
            saved={game.canResume ? game.view : null} onResume={game.resume}
            again={game.view?.ending ? game.view.story.id : null} />
        ) : game.view ? (
          <Play game={game} />
        ) : (
          <View className="flex-1 items-center justify-center gap-4">
            <ActivityIndicator color={colors.gold.fg} />
            <Text className="font-sans text-body text-fg-muted">{ko.loading}</Text>
          </View>
        )}
      </View>
    </View>
  );
}
