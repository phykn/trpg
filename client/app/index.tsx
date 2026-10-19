import Head from 'expo-router/head';
import { ActivityIndicator, Text, View } from 'react-native';
import { useReducedMotion } from 'react-native-reanimated';

import { CommandBar } from '@/components/game/CommandBar';
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
        {starting ? (
          <Start stories={game.stories} busy={game.phase === 'sending'} onCreate={game.create}
            saved={game.canResume ? game.view : null} onResume={game.resume} />
        ) : game.view ? (
          <Play game={game} />
        ) : game.phase === 'blocked' ? (
          <View className="flex-1 justify-end">
            <CommandBar mode="blocked" sent={null} notice={null} placeholder="" onSend={() => undefined}
              onResend={() => undefined} onNew={game.newGame} />
          </View>
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
