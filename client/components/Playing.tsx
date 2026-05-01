import { useAudioPlayer } from 'expo-audio';
import React from 'react';
import { Keyboard, Modal, Pressable, Text, View } from 'react-native';

import { colors, shadow } from '@/design/tokens';

import type { Game } from '@/hooks/useGame';
import { useStoryGraph } from '@/hooks/useStoryGraph';
import { buildPanelSlots } from '@/presenters';
import { buildStoryGraph } from '@/presenters/storyGraph';
import type { PanelAction, PanelSlot } from '@/types/ui';

import { CombatStrip } from './combat';
import { Composer, RollPrompt } from './composer';
import { ContextCard } from './header';
import { HeroStrip } from './hero';
import { Log } from './log';
import { StoryGraphScreen } from './story-graph/StoryGraphScreen';
import { ConfirmDialog } from './ui';

const BGM_SOURCE = require('../assets/audio/bgm.mp3');

type Props = { game: Game };

export function Playing({ game }: Props) {
  const { hero, subject, quest, place, combat, log, pending, streaming, awaitingNarration, suggestions, errorMessage, think, setThink, onSend, onRoll, onStop, goToNewGame } = game;

  const [typing, setTyping] = React.useState(false);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [input, setInput] = React.useState('');
  const [pendingAction, setPendingAction] = React.useState<PanelAction | null>(null);
  const [newGameConfirmOpen, setNewGameConfirmOpen] = React.useState(false);
  const [graphOpen, setGraphOpen] = React.useState(false);
  const [bgmOn, setBgmOn] = React.useState(false);

  const bgm = useAudioPlayer(BGM_SOURCE);
  React.useEffect(() => {
    bgm.loop = true;
  }, [bgm]);

  const toggleBgm = () => {
    if (bgmOn) bgm.pause();
    else bgm.play();
    setBgmOn((v) => !v);
  };

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

  const currentMapGraph = React.useMemo(
    () => buildStoryGraph({ hero, subject, quest, place }),
    [hero, subject, quest, place],
  );
  const miniMapGraph = useStoryGraph(game.gameId, currentMapGraph);

  if (!hero) return null;

  const slots: PanelSlot[] = [
    ...buildPanelSlots({ hero, subject, quest }),
    { id: 'map', chip: { short: '주변' }, panel: null },
  ];
  const rolling = pending !== null && streaming;

  return (
    <View className="flex-1 bg-canvas-default py-2.5 gap-2.5">
      <ContextCard
        slots={slots}
        miniMapGraph={miniMapGraph}
        place={place}
        subject={subject}
        activeId={activeId}
        menuOpen={menuOpen}
        bgmOn={bgmOn}
        onSelect={(id) => setActiveId((prev) => (prev === id ? null : id))}
        onMenuToggle={() => setMenuOpen((v) => !v)}
        onMenuClose={() => setMenuOpen(false)}
        onBgmToggle={toggleBgm}
        onNewGame={() => setNewGameConfirmOpen(true)}
        onGraph={() => setGraphOpen(true)}
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

      <Modal
        transparent
        visible={graphOpen}
        animationType="fade"
        onRequestClose={() => setGraphOpen(false)}
      >
        <Pressable
          onPress={() => setGraphOpen(false)}
          className="flex-1 items-center justify-start px-4"
          style={{ backgroundColor: 'rgba(24, 20, 14, 0.62)', paddingTop: 170 }}
        >
          <Pressable
            onPress={(e) => e.stopPropagation()}
            className="bg-canvas-subtle border border-border-default rounded-md w-full"
            style={{ maxWidth: 560, maxHeight: '92%', ...shadow.floating }}
          >
            <View className="px-3 py-3">
              <StoryGraphScreen
                embedded
                onClose={() => setGraphOpen(false)}
                onAction={(action) => {
                  setGraphOpen(false);
                  onSend(action.intent);
                }}
              />
            </View>
          </Pressable>
        </Pressable>
      </Modal>

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
            title: '새 게임',
            blurb: '현재 이어 하던 세션 연결을 해제하고 새 게임 설정 화면으로 돌아갑니다.',
            risk: { label: '세션 연결 해제', tone: 'bad' },
            confirmLabel: '새 게임',
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
        suggestions={!streaming && !pending ? suggestions : []}
        onPickSuggestion={onSend}
      />

      {combat ? <CombatStrip combat={combat} /> : null}

      {pending ? (
        <RollPrompt pending={pending} onRoll={onRoll} onStop={onStop} rolling={rolling} />
      ) : (
        <Composer
          input={input}
          setInput={setInput}
          onSend={onSend}
          onStop={onStop}
          focused={typing}
          streaming={streaming}
          think={think}
          onToggleThink={() => setThink((v) => !v)}
        />
      )}

      {errorMessage ? (
        <View className="mx-5 rounded-sm border border-danger-fg bg-canvas-subtle px-3 py-2">
          <Text className="font-sans text-caption text-danger-fg">
            {errorMessage}
          </Text>
        </View>
      ) : null}
    </View>
  );
}
