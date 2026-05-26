import React from 'react';
import { Keyboard, Platform, Pressable, Text, View, type KeyboardEvent } from 'react-native';

import { CombatStrip } from '@/logic/combat';
import { DiscoveriesPanel } from '@/components/discoveries/DiscoveriesPanel';
import { buildDecisionState, DecisionStateStrip } from '@/logic/decision-state';
import { Log } from '@/logic/log';
import { RollPanel } from '@/logic/roll';
import { buildNearbyPanel } from '@/logic/story-graph';
import type { Game } from '@/logic/game/useGame';
import { buildPanelSlots, type PanelAction, type PanelSlot } from '@/logic/info-panel';

import { Composer, GameOverPanel, LevelUpPrompt } from '@/logic/composer';
import { ContextCard, IconButton, ICON_PATH } from '@/logic/info-panel';
import { useBgm } from '@/logic/audio';
import { ConfirmDialog } from '@/components/ui';
import { ko } from '@/locale/ko';

type Props = { game: Game };

type NavigatorWithVirtualKeyboard = Navigator & {
  virtualKeyboard?: EventTarget & { boundingRect: DOMRectReadOnly };
};

function isEditableElementFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return tag === 'input' || tag === 'textarea' || el.getAttribute('contenteditable') === 'true';
}

export function Playing({ game }: Props) {
  const { hero, subject, chapter, quest, questOffers, place, combat, discoveries, storyGraph, log, pendingConfirmation, pendingRoll, streaming, awaitingNarration, gameOver, suggestions, errorMessage, onSend, onQuestAction, onGraphAction, onCombatCommand, onConfirmPending, onRollPending, onStop, goToNewGame, levelUpOpen, levelUpChoices, levelUpLoading, openLevelUp, cancelLevelUp, commitLevelUp } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [input, setInput] = React.useState('');
  const [pendingAction, setPendingAction] = React.useState<PanelAction | null>(null);
  const [newGameConfirmOpen, setNewGameConfirmOpen] = React.useState(false);
  const [nearbyOpen, setNearbyOpen] = React.useState(false);
  const [bottomOverlayHeight, setBottomOverlayHeight] = React.useState(0);
  const [keyboardOverlayHeight, setKeyboardOverlayHeight] = React.useState(0);
  const [playSurfaceHeight, setPlaySurfaceHeight] = React.useState(0);
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

  const setNearbyOpenFromComposer = (open: boolean) => {
    if (open) setActiveId(null);
    setNearbyOpen(open);
  };

  const openLevelUpFromComposer = () => {
    Keyboard.dismiss();
    closePopups();
    openLevelUp();
  };

  const runPanelAction = (action: PanelAction) => {
    if (action.confirm) {
      setPendingAction(action);
    } else {
      runAction(action);
    }
  };

  React.useEffect(() => {
    if (Platform.OS === 'web') {
      const updateWebKeyboardOverlayHeight = () => {
        const webNavigator = navigator as NavigatorWithVirtualKeyboard;
        const keyboardHeight = webNavigator.virtualKeyboard?.boundingRect.height ?? 0;
        const visualViewportHeight = isEditableElementFocused() && window.visualViewport
          ? Math.max(0, window.innerHeight - window.visualViewport.height - window.visualViewport.offsetTop)
          : 0;
        const nextHeight = Math.max(keyboardHeight, visualViewportHeight);
        setTyping(nextHeight > 0);
        setKeyboardOverlayHeight(nextHeight);
      };
      const webNavigator = navigator as NavigatorWithVirtualKeyboard;
      webNavigator.virtualKeyboard?.addEventListener('geometrychange', updateWebKeyboardOverlayHeight);
      window.visualViewport?.addEventListener('resize', updateWebKeyboardOverlayHeight);
      window.visualViewport?.addEventListener('scroll', updateWebKeyboardOverlayHeight);
      updateWebKeyboardOverlayHeight();
      return () => {
        webNavigator.virtualKeyboard?.removeEventListener('geometrychange', updateWebKeyboardOverlayHeight);
        window.visualViewport?.removeEventListener('resize', updateWebKeyboardOverlayHeight);
        window.visualViewport?.removeEventListener('scroll', updateWebKeyboardOverlayHeight);
      };
    }

    const show = Keyboard.addListener('keyboardDidShow', (ev: KeyboardEvent) => {
      setTyping(true);
      setKeyboardOverlayHeight(ev.endCoordinates.height);
    });
    const hide = Keyboard.addListener('keyboardDidHide', () => {
      setTyping(false);
      setKeyboardOverlayHeight(0);
    });
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  React.useEffect(() => {
    if (typing) {
      setActiveId(null);
      setNearbyOpen(false);
    }
  }, [typing]);

  React.useEffect(() => {
    if (game.scenarioCompleted) {
      setNearbyOpen(false);
    }
  }, [game.scenarioCompleted]);

  const nearby = React.useMemo(() => buildNearbyPanel(storyGraph), [storyGraph]);
  const visibleNearby = game.scenarioCompleted ? null : nearby;
  const visibleSuggestions = game.scenarioCompleted ? [] : suggestions;
  const lastLogEntry = log[log.length - 1];
  const latestCues = lastLogEntry?.kind === 'gm' ? lastLogEntry.cues ?? [] : [];
  const decisionStateItems = React.useMemo(
    () => buildDecisionState({
      place,
      quest,
      combat,
      subject,
      heroVitals: hero ? {
        level: hero.level,
        exp: hero.exp,
        expMax: hero.expMax,
        hp: hero.hp,
        hpMax: hero.hpMax,
        mp: hero.mp,
        mpMax: hero.mpMax,
      } : undefined,
      heroStatus: hero?.status ?? [],
      latestCues,
      scenarioCompleted: game.scenarioCompleted,
    }),
    [
      combat,
      game.scenarioCompleted,
      hero?.hp,
      hero?.hpMax,
      hero?.level,
      hero?.exp,
      hero?.expMax,
      hero?.mp,
      hero?.mpMax,
      hero?.status,
      latestCues,
      place,
      quest,
      subject,
    ],
  );
  const slots: PanelSlot[] = React.useMemo(
    () => {
      if (!hero) return [];
      return [
        ...buildPanelSlots({ hero, subject, chapter, scenarioCompleted: game.scenarioCompleted, quest, questOffers }),
      ];
    },
    [
      chapter,
      game.scenarioCompleted,
      hero,
      quest,
      questOffers,
      subject,
    ],
  );

  if (!hero) return null;
  const showRollPanel = pendingRoll !== null && !streaming;
  return (
    <View
      className="flex-1 bg-canvas-default py-2.5 gap-2.5"
      onLayout={(ev) => {
        const nextHeight = ev.nativeEvent.layout.height;
        setPlaySurfaceHeight((prev) => Math.max(prev, nextHeight));
      }}
      style={{
        height: keyboardOverlayHeight > 0 && playSurfaceHeight > 0 ? playSurfaceHeight : undefined,
      }}
    >
      <ContextCard
        slots={slots}
        activeId={activeId}
        actionDisabled={streaming || pendingConfirmation !== null || pendingRoll !== null}
        onAction={runPanelAction}
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
          setNearbyOpen(false);
          setActiveId((prev) => {
            const next = prev === id ? null : id;
            return next;
          });
        }}
      />

      <DecisionStateStrip items={decisionStateItems} />

      <DiscoveriesPanel discoveries={discoveries} />

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
        bottomInset={bottomOverlayHeight}
        keyboardOverlayActive={keyboardOverlayHeight > 0}
      />

      {errorMessage ? (
        <View className="mx-5 rounded-sm border border-danger-fg bg-canvas-subtle px-3 py-2">
          <Text className="font-sans text-caption text-danger-fg">
            {errorMessage}
          </Text>
        </View>
      ) : null}

      <View
        onLayout={(ev) => setBottomOverlayHeight(ev.nativeEvent.layout.height)}
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: keyboardOverlayHeight,
          zIndex: activeId !== null || nearbyOpen ? 10 : 0,
        }}
      >
        {gameOver ? (
          <GameOverPanel onRestart={goToNewGame} />
        ) : showRollPanel ? (
          <RollPanel
            roll={pendingRoll}
            onRoll={onRollPending}
            disabled={pendingConfirmation !== null}
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
              actionDisabled={streaming || pendingConfirmation !== null || pendingRoll !== null}
            />
            <Composer
              input={input}
              setInput={setInput}
              onSend={onSend}
              onStop={onStop}
              streaming={streaming}
              locked={pendingConfirmation !== null || pendingRoll !== null}
            />
          </View>
        ) : game.scenarioCompleted ? null : levelUpOpen ? (
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
            suggestions={visibleSuggestions}
            quickActions={hero.canLevelUp && !game.scenarioCompleted ? [{
              id: 'level-up',
              label: ko.level.title,
              onPress: openLevelUpFromComposer,
              disabled: streaming || pendingConfirmation !== null || pendingRoll !== null,
            }] : []}
            nearby={visibleNearby}
            nearbyOpen={nearbyOpen}
            onNearbyOpenChange={setNearbyOpenFromComposer}
            onNearbyAction={(action) => {
              runPanelAction(action);
            }}
          />
        )}
      </View>
    </View>
  );
}
