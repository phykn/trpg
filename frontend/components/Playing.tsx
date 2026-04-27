import React from 'react';
import { Keyboard, View } from 'react-native';

import type { Game } from '@/hooks/useGame';
import { buildPanelSlots } from '@/presenters';

import { CombatStrip } from './combat';
import { Composer } from './composer';
import { ContextCard } from './header';
import { HeroPill } from './hero';
import { Log } from './log';

type Props = { game: Game };

export function Playing({ game }: Props) {
  const { hero, subject, quest, place, combat, log, pending, streaming, awaitingNarration, suggestions, onSend, onRoll, onStop, goToNewGame } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [heroOpen, setHeroOpen] = React.useState(false);
  const [input, setInput] = React.useState('');

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
        onNewGame={goToNewGame}
      />

      <Log
        log={log}
        rolling={rolling}
        typing={awaitingNarration}
        suggestions={!streaming && !pending ? suggestions : []}
        onPickSuggestion={setInput}
      />

      <HeroPill hero={hero} expanded={heroOpen} onToggle={() => setHeroOpen((v) => !v)} />

      {combat ? <CombatStrip combat={combat} /> : null}

      <Composer
        input={input}
        setInput={setInput}
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
