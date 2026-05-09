import React from 'react';
import { Keyboard, KeyboardAvoidingView, Platform, Pressable, Text, View } from 'react-native';

import { useBgm } from '@/logic/audio';
import { CombatStrip } from '@/logic/combat';
import { Log } from '@/logic/log';
import { useStoryGraph } from '@/logic/story-graph';
import type { Game } from '@/logic/game/useGame';
import { buildPanelSlots } from '@/logic/info-panel';
import type { PanelAction, PanelSlot } from '@/logic/info-panel';

import { Composer, GameOverPanel, LevelUpPrompt, RollPrompt } from '@/logic/composer';
import { ContextCard } from '@/logic/info-panel';
import { HeroStrip } from '@/logic/hero';
import { ConfirmDialog } from '@/components/ui';
import { ko } from '@/locale/ko';

type Props = { game: Game };

export function Playing({ game }: Props) {
  const { hero, subject, quest, place, combat, storyGraph, log, pending, pendingConfirmation, streaming, awaitingNarration, gameOver, suggestions, errorMessage, onSend, onQuestAction, onGraphAction, onConfirmPending, onRoll, onStop, goToNewGame, hasUnseenLocation, markLocationSeen, hasUnseenQuest, markQuestSeen, hasUnseenSubject, markSubjectSeen, levelUpOpen, levelUpCandidates, openLevelUp, cancelLevelUp, commitLevelUp } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [input, setInput] = React.useState('');
  const [pendingAction, setPendingAction] = React.useState<PanelAction | null>(null);
  const [newGameConfirmOpen, setNewGameConfirmOpen] = React.useState(false);
  const { bgmOn, toggle: toggleBgm } = useBgm();

  const runAction = (action: PanelAction) => {
    setActiveId(null);
    if (action.kind === 'text') {
      onSend(action.text);
    } else if (action.kind === 'graph_action') {
      onGraphAction(action.graphAction, action.textFallback);
    } else {
      onQuestAction(action.questAction.kind, action.questAction.quest_id);
    }
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

  const { graph: miniMapGraph, unseenNodeIds: unseenMapNodeIds, markNodeSeen } = useStoryGraph(game.gameId, storyGraph);

  if (!hero) return null;

  const slots: PanelSlot[] = [
    ...buildPanelSlots({ hero, subject, quest }, { onLevelUpOpen: openLevelUp, questDot: hasUnseenQuest, subjectDot: hasUnseenSubject }),
    { id: 'map', chip: { short: ko.panel.neighborhood, dot: hasUnseenLocation }, panel: null },
  ];
  const rolling = pending !== null && streaming;

  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <ContextCard
        slots={slots}
        miniMapGraph={miniMapGraph}
        place={place}
        activeId={activeId}
        menuOpen={menuOpen}
        bgmOn={bgmOn}
        onSelect={(id) => {
          setActiveId((prev) => {
            const next = prev === id ? null : id;
            if (id === 'map' && next === id) markLocationSeen();
            if (id === 'quest' && next === id) markQuestSeen();
            if (id === 'person' && next === id) markSubjectSeen();
            return next;
          });
        }}
        onMenuToggle={() => setMenuOpen((v) => !v)}
        onMenuClose={() => setMenuOpen(false)}
        onBgmToggle={toggleBgm}
        onNewGame={() => setNewGameConfirmOpen(true)}
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

      {pendingConfirmation && (
        <ConfirmDialog
          info={{
            title: pendingConfirmation.title,
            subtitle: pendingConfirmation.targetLabel ?? undefined,
            blurb: pendingConfirmation.body,
            confirmLabel: pendingConfirmation.confirmLabel,
            cancelLabel: pendingConfirmation.cancelLabel,
          }}
          onConfirm={() => onConfirmPending('confirm')}
          onCancel={() => onConfirmPending('cancel')}
        />
      )}

      {newGameConfirmOpen && (
        <ConfirmDialog
          info={{
            title: ko.menu.newGame,
            blurb: ko.newGame.leaveBlurb,
            confirmLabel: ko.action.start,
          }}
          onConfirm={() => {
            setNewGameConfirmOpen(false);
            goToNewGame();
          }}
          onCancel={() => setNewGameConfirmOpen(false)}
        />
      )}

      <HeroStrip hero={hero} />

      <Log
        log={log}
        rolling={rolling}
        typing={awaitingNarration}
        suggestions={!gameOver && !streaming && !pending && !pendingConfirmation ? suggestions : []}
        onPickSuggestion={onSend}
      />

      {combat ? <CombatStrip combat={combat} /> : null}

      {errorMessage ? (
        <View className="mx-5 rounded-sm border border-danger-fg bg-canvas-subtle px-3 py-2">
          <Text className="font-sans text-caption text-danger-fg">
            {errorMessage}
          </Text>
        </View>
      ) : null}

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
        {gameOver ? (
          <GameOverPanel onRestart={goToNewGame} />
        ) : pending ? (
          <RollPrompt pending={pending} onRoll={onRoll} onStop={onStop} rolling={rolling} />
        ) : levelUpOpen ? (
          <LevelUpPrompt
            hero={hero}
            candidates={levelUpCandidates}
            onCommit={commitLevelUp}
            onCancel={cancelLevelUp}
          />
        ) : (
          <Composer
            input={input}
            setInput={setInput}
            onSend={onSend}
            onStop={onStop}
            streaming={streaming}
          />
        )}
      </KeyboardAvoidingView>
    </View>
  );
}
