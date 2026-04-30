import React from 'react';
import { Keyboard, Pressable, View } from 'react-native';

import type { Game } from '@/hooks/useGame';
import { buildPanelSlots } from '@/presenters';
import type { PanelAction } from '@/types/ui';

import { CombatStrip } from './combat';
import { Composer, RollPrompt } from './composer';
import { ContextCard } from './header';
import { HeroStrip } from './hero';
import { Log } from './log';
import { ConfirmDialog } from './ui';

type Props = { game: Game };

export function Playing({ game }: Props) {
  const { hero, subject, quest, place, combat, log, pending, streaming, awaitingNarration, suggestions, onSend, onRoll, onStop, goToNewGame } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [input, setInput] = React.useState('');
  const [pendingAction, setPendingAction] = React.useState<PanelAction | null>(null);

  const runAction = (action: PanelAction) => {
    setActiveId(null);
    onSend(action.intent);
  };

  const closePopups = () => {
    setActiveId(null);
    setMenuOpen(false);
  };

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
      setMenuOpen(false);
    }
  }, [typing]);

  if (!hero) return null;

  const slots = buildPanelSlots({ hero, subject, quest, place });
  const rolling = pending !== null && streaming;

  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <ContextCard
        slots={slots}
        activeId={activeId}
        menuOpen={menuOpen}
        onSelect={(id) => setActiveId((prev) => (prev === id ? null : id))}
        onCollapse={() => setActiveId(null)}
        onMenuToggle={() => setMenuOpen((v) => !v)}
        onMenuClose={() => setMenuOpen(false)}
        onNewGame={goToNewGame}
        onAction={(action) => {
          if (action.confirm) {
            setPendingAction(action);
          } else {
            runAction(action);
          }
        }}
      />

      {(activeId !== null || menuOpen) && (
        <Pressable
          onPress={closePopups}
          style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9 }}
        />
      )}

      {pendingAction?.confirm && (
        <ConfirmDialog
          info={pendingAction.confirm}
          onConfirm={() => {
            const action = pendingAction;
            setPendingAction(null);
            runAction(action);
          }}
          onCancel={() => setPendingAction(null)}
        />
      )}

      <HeroStrip hero={hero} />

      <Log
        log={log}
        rolling={rolling}
        typing={awaitingNarration}
        suggestions={!streaming && !pending ? suggestions : []}
        onPickSuggestion={onSend}
      />

      {combat ? <CombatStrip combat={combat} /> : null}

      {pending ? <RollPrompt pending={pending} onRoll={onRoll} rolling={rolling} /> : null}

      <Composer
        input={input}
        setInput={setInput}
        onSend={onSend}
        onStop={onStop}
        focused={typing}
        streaming={streaming}
      />
    </View>
  );
}
