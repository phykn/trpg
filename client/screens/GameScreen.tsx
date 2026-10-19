import { useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import Head from 'expo-router/head';

import { Journal } from '@/components/game/Journal';
import { SceneHeader } from '@/components/game/SceneHeader';
import { Sheet } from '@/components/game/Sheet';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Reader } from '@/components/ui/Reader';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { useGame } from '@/logic/useGame';
import { useViewportHeight } from '@/logic/useViewportHeight';
import { Play } from './Play';
import { Start } from './Start';

export function GameScreen() {
  const game = useGame();
  const height = useViewportHeight();
  const [dialog, setDialog] = useState<'sheet' | 'journal' | null>(null);
  const view = game.view;
  const playing = view && !game.creating;

  return (
    <View className="items-center bg-canvas-inset" style={{ height }}>
      <Head><title>{view?.title ?? ko.brand}</title></Head>
      <View className="mobile-frame w-full max-w-mobile flex-1 min-h-0 border-x border-border-default bg-canvas-default">
        {playing ? <SceneHeader view={view} onSheet={() => setDialog('sheet')} onJournal={() => setDialog('journal')} /> : (
          <View className="border-b border-border-default px-6 py-4">
            <Text className="font-sans-semibold text-title text-fg-default">{ko.brand}</Text>
          </View>
        )}
        {game.error ? (
          <View className="flex-1 min-h-0 gap-5 px-6 py-5">
            <Text accessibilityRole="alert" className="font-sans-semibold text-title text-danger-fg">{ko.recovery}</Text>
            <Reader key={game.error} text={game.error} disabled={game.busy} doneLabel={ko.retry} onDone={() => void game.retry()} />
            {!view && game.catalog ? <Button label={ko.newGame} disabled={game.busy} onPress={game.openNew} /> : null}
          </View>
        ) : game.creating && game.catalog ? (
          <Start catalog={game.catalog} busy={game.busy} canResume={!!view} onStart={game.start} onResume={game.resume} />
        ) : playing ? (
          <Play view={view} narration={game.narration} notice={game.notice} blocked={game.busy || game.needsSync}
            onSend={(command) => void game.send(command)} onRetry={() => void game.retryNarration()}
            onDismiss={game.dismissNotice} onNew={game.openNew} />
        ) : (
          <View className="flex-1 items-center justify-center gap-4 px-6">
            <ActivityIndicator color={colors.gold.fg} />
            <Text className="font-sans text-body text-fg-muted">{ko.loading}</Text>
          </View>
        )}
        {game.busy && view ? (
          <View className="absolute bottom-0 left-0 right-0 items-center bg-canvas-floating py-1" style={{ pointerEvents: 'none' }}>
            <Text accessibilityLiveRegion="polite" className="font-sans text-caption text-gold-fg">{ko.saving}</Text>
          </View>
        ) : null}
      </View>
      {dialog && view ? (
        <Dialog title={dialog === 'sheet' ? ko.sheet : ko.journal} onClose={() => setDialog(null)}>
          {dialog === 'sheet' ? <Sheet view={view} onNew={() => { setDialog(null); game.openNew(); }} /> : <Journal view={view} />}
        </Dialog>
      ) : null}
    </View>
  );
}
