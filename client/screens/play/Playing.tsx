import React from 'react';
import { Keyboard, KeyboardAvoidingView, Platform, Pressable, Text, View } from 'react-native';

import { CombatStrip } from '@/logic/combat';
import { Log } from '@/logic/log';
import { RollPanel } from '@/components/roll/RollPanel';
import { buildNearbyPanel, useStoryGraph } from '@/logic/story-graph';
import type { Game } from '@/logic/game/useGame';
import { buildPanelSlots, type PanelAction, type PanelSlot } from '@/logic/info-panel';

import { Composer, GameOverPanel, LevelUpPrompt } from '@/logic/composer';
import { ContextCard, IconButton, ICON_PATH } from '@/logic/info-panel';
import { HeroStrip } from '@/logic/hero';
import { useBgm } from '@/logic/audio';
import { ConfirmDialog } from '@/components/ui';
import { ko } from '@/locale/ko';

type Props = { game: Game };

export function Playing({ game }: Props) {
  const { hero, subject, quest, questOffers, place, combat, storyGraph, log, pendingConfirmation, pendingRoll, streaming, awaitingNarration, gameOver, suggestions, errorMessage, onSend, onQuestAction, onGraphAction, onCombatCommand, onConfirmPending, onRollPending, onStop, goToNewGame, hasUnseenLocation, markLocationSeen, hasUnseenQuest, markQuestSeen, hasUnseenSubject, markSubjectSeen, levelUpOpen, levelUpChoices, levelUpLoading, openLevelUp, cancelLevelUp, commitLevelUp } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [input, setInput] = React.useState('');
  const [pendingAction, setPendingAction] = React.useState<PanelAction | null>(null);
  const [newGameConfirmOpen, setNewGameConfirmOpen] = React.useState(false);
  const [nearbyOpen, setNearbyOpen] = React.useState(false);
  const { bgmOn, toggle: toggleBgm } = useBgm();

  const runAction = (action: PanelAction) => {
    setActiveId(null);
    if (action.kind === 'text') {
      onSend(action.text);
    } else if (action.kind === 'graph_action') {
      onGraphAction(action.graphAction, action.label);
    } else if (action.kind === 'combat_command') {
      onCombatCommand(action.combatCommand, action.label);
    } else {
      onQuestAction(action.questAction.kind, action.questAction.quest_id, action.label);
    }
  };

  const closePopups = () => {
    setActiveId(null);
    setNearbyOpen(false);
  };

  const openLevelUpFromComposer = () => {
    Keyboard.dismiss();
    closePopups();
    openLevelUp();
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
    }
  }, [typing]);

  const { graph: miniMapGraph } = useStoryGraph(game.gameId, storyGraph);
  const nearby = React.useMemo(() => buildNearbyPanel(miniMapGraph), [miniMapGraph]);

  if (!hero) return null;

  const slots: PanelSlot[] = [
    { id: 'map', chip: { short: ko.table.map, dot: hasUnseenLocation }, panel: null },
    ...buildPanelSlots(
      { hero, subject, quest, questOffers },
      { questDot: hasUnseenQuest, subjectDot: hasUnseenSubject },
    ),
  ];
  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <HeroStrip hero={hero} />

      <ContextCard
        slots={slots}
        miniMapGraph={miniMapGraph}
        place={place}
        activeId={activeId}
        leading={(
          <IconButton
            d={ICON_PATH.newGame}
            label={ko.menu.newGame}
            onPress={() => setNewGameConfirmOpen(true)}
          />
        )}
        trailing={(
          <IconButton
            d={bgmOn ? ICON_PATH.volumeOn : ICON_PATH.volumeOff}
            label={bgmOn ? ko.menu.soundOff : ko.menu.soundOn}
            active={bgmOn}
            onPress={toggleBgm}
          />
        )}
        onSelect={(id) => {
          setActiveId((prev) => {
            const next = prev === id ? null : id;
            if (id === 'map' && next === id) markLocationSeen();
            if (id === 'notes' && next === id) {
              markQuestSeen();
              markSubjectSeen();
            }
            return next;
          });
        }}
        onAction={(action) => {
          if (action.confirm) {
            setPendingAction(action);
          } else {
            runAction(action);
          }
        }}
      />

      {activeId !== null && (
        <Pressable
          onPress={closePopups}
          style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9 }}
        />
      )}

      {nearbyOpen && activeId === null && (
        <Pressable
          onPress={closePopups}
          style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 7 }}
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

      {newGameConfirmOpen && (
        <ConfirmDialog
          info={{
            title: ko.menu.newGame,
            blurb: ko.newGame.leaveBlurb,
            confirmLabel: ko.gameOver.restart,
            cancelLabel: ko.level.cancel,
          }}
          onConfirm={() => {
            setNewGameConfirmOpen(false);
            goToNewGame();
          }}
          onCancel={() => setNewGameConfirmOpen(false)}
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

      <Log
        log={log}
        typing={awaitingNarration}
      />

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
        style={{ zIndex: activeId !== null || nearbyOpen ? 10 : 0 }}
      >
        {gameOver ? (
          <GameOverPanel onRestart={goToNewGame} />
        ) : pendingRoll ? (
          <RollPanel
            roll={pendingRoll}
            onRoll={onRollPending}
            disabled={streaming || pendingConfirmation !== null}
          />
        ) : combat ? (
          <View>
            <CombatStrip
              combat={combat}
              onAction={(action) => {
                if (action.confirm) {
                  setPendingAction(action);
                } else {
                  runAction(action);
                }
              }}
              actionDisabled={streaming || pendingConfirmation !== null}
            />
            <Composer
              input={input}
              setInput={setInput}
              onSend={onSend}
              onStop={onStop}
              streaming={streaming}
              locked={pendingConfirmation !== null}
            />
          </View>
        ) : levelUpOpen ? (
          <LevelUpPrompt
            hero={hero}
            choices={levelUpChoices}
            loading={levelUpLoading}
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
            suggestions={suggestions}
            quickActions={hero.canLevelUp ? [{
              id: 'level-up',
              label: ko.level.title,
              onPress: openLevelUpFromComposer,
              disabled: streaming || pendingConfirmation !== null,
            }] : []}
            nearby={nearby}
            nearbyOpen={nearbyOpen}
            onNearbyOpenChange={setNearbyOpen}
            onNearbyAction={(action) => {
              if (action.confirm) {
                setPendingAction(action);
              } else {
                runAction(action);
              }
            }}
          />
        )}
      </KeyboardAvoidingView>
    </View>
  );
}
