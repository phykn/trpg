import { useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import Head from 'expo-router/head';

import { PlayerStatus } from '@/components/game/PlayerStatus';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Reader } from '@/components/ui/Reader';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { useGame } from '@/logic/useGame';
import { useViewportHeight } from '@/logic/useViewportHeight';
import { Adventure } from './Adventure';
import { Arrival } from './Arrival';

export function GameScreen() {
  const game = useGame();
  const height = useViewportHeight();
  const [menu, setMenu] = useState(false);
  const view = game.view;
  const playing = view && !game.creating;

  return (
    <View className="items-center bg-canvas-inset" style={{ height }}>
      <Head><title>{game.catalog?.title ?? ko.brand}</title></Head>
      <View className="mobile-frame w-full max-w-mobile flex-1 min-h-0 border-x border-border-default bg-canvas-default">
        {playing ? <PlayerStatus view={view} onMenu={() => setMenu(true)} /> : (
          <View className="flex-row items-center justify-between gap-3 border-b border-border-default px-6 py-4">
            <Text className="font-sans-semibold text-title text-fg-default">{ko.brand}</Text>
            <Text className="font-mono text-caption text-gold-fg">01 / {ko.chapter}</Text>
          </View>
        )}
        {game.error ? (
          <View className="flex-1 min-h-0 gap-5 px-6 py-5">
            <Text accessibilityRole="alert" className="font-sans-semibold text-title text-danger-fg">{ko.recovery}</Text>
            <Reader key={game.error} text={game.error} disabled={game.busy} doneLabel={ko.retry} onDone={() => void game.retry()} />
            {!view && game.catalog ? <Button label={ko.newGame} disabled={game.busy} onPress={game.openNew} /> : null}
          </View>
        ) : game.creating && game.catalog ? (
          <Arrival catalog={game.catalog} busy={game.busy} canResume={!!view} onStart={game.start} onResume={game.resume} />
        ) : playing ? (
          <Adventure key={`${view.game_id}:${view.revision}`} view={view} blocked={game.busy || game.needsSync} onChoose={game.choose} onNew={game.openNew} />
        ) : (
          <View className="flex-1 items-center justify-center gap-4 px-6">
            <ActivityIndicator color={colors.gold.fg} />
            <Text className="font-sans text-body text-fg-muted">{ko.loading}</Text>
          </View>
        )}
        {game.busy && (view || game.catalog) ? <View className="absolute bottom-0 left-0 right-0 items-center bg-canvas-floating py-1" style={{ pointerEvents: 'none' }}><Text accessibilityLiveRegion="polite" className="font-sans text-caption text-gold-fg">{ko.saving}</Text></View> : null}
      </View>
      {menu && view ? (
        <Dialog title={ko.menu} onClose={() => setMenu(false)}>
          <Reader text={[view.player_name, view.role, view.alert, ko.readHelp, ko.saveHelp].join('\n\n')} doneLabel={ko.newGame} disabled={game.busy} onDone={() => { setMenu(false); game.openNew(); }} />
        </Dialog>
      ) : null}
    </View>
  );
}
