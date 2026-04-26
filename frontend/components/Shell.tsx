import React from 'react';
import { ActivityIndicator, Keyboard, Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { useGame } from '@/hooks/useGame';
import { buildPanelSlots } from '@/presenters';

import { CombatStrip } from './combat';
import { Composer } from './composer';
import { ContextCard } from './header';
import { HeroPill } from './hero';
import { Log } from './log';
import { NewGame } from './NewGame';

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

type PlayingProps = { game: ReturnType<typeof useGame> };

function Playing({ game }: PlayingProps) {
  const { hero, subject, quest, place, combat, log, pending, streaming, onSend, onRoll, onStop } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>('person');
  const [heroOpen, setHeroOpen] = React.useState(false);

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', () => setTyping(true));
    const hide = Keyboard.addListener('keyboardDidHide', () => setTyping(false));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  React.useEffect(() => {
    if (typing) {
      setActiveId(null);
      setHeroOpen(false);
    }
  }, [typing]);

  if (!hero) return null;

  const slots = buildPanelSlots({ subject, quest, place });
  const rollEnabled = pending !== null;
  const rolling = rollEnabled && streaming;

  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <ContextCard
        slots={slots}
        activeId={activeId}
        onSelect={(id) => setActiveId((prev) => (prev === id ? null : id))}
        onCollapse={() => setActiveId(null)}
      />

      <Log log={log} rolling={rolling} />

      <HeroPill hero={hero} expanded={heroOpen} onToggle={() => setHeroOpen((v) => !v)} />

      {combat ? <CombatStrip combat={combat} /> : null}

      <Composer
        onSend={onSend}
        onRoll={onRoll}
        onStop={onStop}
        rolling={rolling}
        focused={typing}
        rollEnabled={rollEnabled}
        streaming={streaming}
      />
    </View>
  );
}
