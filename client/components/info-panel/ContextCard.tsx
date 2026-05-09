import React from 'react';
import { PanResponder, Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';

import { Chip, Surface } from '@/components/ui';
import {
  MiniMapPanel,
  StoryGraphScreen,
  type StoryGraphModel,
  type Place,
} from '@/logic/story-graph';

import type { PanelAction, PanelSlot } from '@/logic/info-panel/types';

import { IconButton, ICON_PATH } from '@/components/info-panel/IconButton';
import { PanelBody } from '@/components/info-panel/PanelBody';

const FLOAT_BUFFER = 540;

export function ContextCard({ slots, miniMapGraph, place, activeId, menuOpen, bgmOn, onSelect, onMenuToggle, onMenuClose, onBgmToggle, onNewGame, onAction }: {
  slots: PanelSlot[];
  miniMapGraph: StoryGraphModel;
  place: Place | null;
  activeId: string | null;
  menuOpen: boolean;
  bgmOn: boolean;
  onSelect: (id: string) => void;
  onMenuToggle: () => void;
  onMenuClose: () => void;
  onBgmToggle: () => void;
  onNewGame?: () => void;
  onAction?: (action: PanelAction) => void;
}) {
  const activeSlot = slots.find((s) => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;
  const miniMapOpen = activeId === 'map';
  const graphOpen = activeId === 'graph';
  const [chipBarHeight, setChipBarHeight] = React.useState(48);
  const floating = panel || miniMapOpen || graphOpen || menuOpen;

  const panResponder = React.useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => false,
        onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) > 8 || Math.abs(g.dy) > 8,
        onPanResponderTerminationRequest: () => false,
        onPanResponderMove: () => {},
        onPanResponderRelease: () => {},
        onPanResponderTerminate: () => {},
      }),
    [],
  );

  return (
    <View
      className="mx-5"
      pointerEvents="box-none"
      style={[
        { zIndex: 10 },
        floating ? { paddingBottom: FLOAT_BUFFER, marginBottom: -FLOAT_BUFFER } : null,
      ]}
    >
      <Surface
        onLayout={(e) => setChipBarHeight(e.nativeEvent.layout.height)}
        className="flex-row p-2 gap-1 items-center"
      >
        <IconButton d={ICON_PATH.menu} label={ko.menu.menuLabel} onPress={onMenuToggle} />
        <View className="flex-1 flex-row gap-1">
          {slots.map((s) => (
            <Chip
              key={s.id}
              variant="tab"
              label={s.chip.short}
              active={s.id === activeId}
              dot={s.chip.dot}
              onPress={() => onSelect(s.id)}
            />
          ))}
        </View>
        <IconButton
          d={ICON_PATH.map}
          label={ko.panel.fullMap}
          active={graphOpen}
          onPress={() => onSelect('graph')}
        />
      </Surface>
      {panel && (
        <Surface
          variant="floating"
          className="overflow-hidden"
          style={{ position: 'absolute', top: chipBarHeight + 4, left: 0, right: 0, maxHeight: FLOAT_BUFFER }}
          {...panResponder.panHandlers}
        >
          <PanelBody panel={panel} onAction={onAction} />
        </Surface>
      )}
      {miniMapOpen && (
        <Surface
          variant="floating"
          className="overflow-hidden"
          style={{ position: 'absolute', top: chipBarHeight + 4, left: 0, right: 0, maxHeight: FLOAT_BUFFER }}
          {...panResponder.panHandlers}
        >
          <MiniMapPanel
            graph={miniMapGraph}
            place={place}
            onAction={onAction}
          />
        </Surface>
      )}
      {graphOpen && (
        <Surface
          variant="floating"
          className="overflow-hidden"
          style={{ position: 'absolute', top: chipBarHeight + 4, left: 0, right: 0, maxHeight: FLOAT_BUFFER }}
          {...panResponder.panHandlers}
        >
          <StoryGraphScreen
            onAction={(action) => {
              onSelect('graph');
              onAction?.(action);
            }}
          />
        </Surface>
      )}
      {menuOpen && (
        <Surface
          variant="floating"
          className="overflow-hidden"
          style={{
            position: 'absolute',
            top: chipBarHeight + 4,
            left: 0,
            minWidth: 112,
            maxHeight: FLOAT_BUFFER,
            zIndex: 20,
          }}
        >
          <Pressable
            onPress={() => {
              onMenuClose();
              onNewGame?.();
            }}
            accessibilityRole="button"
            accessibilityLabel={ko.menu.newGame}
            className="px-3 py-2"
          >
            <Text className="font-sans text-body text-fg-default">{ko.menu.newGame}</Text>
          </Pressable>
          <Pressable
            onPress={() => {
              onMenuClose();
              onBgmToggle();
            }}
            accessibilityRole="button"
            accessibilityLabel={bgmOn ? ko.menu.soundOff : ko.menu.soundOn}
            className="px-3 py-2"
          >
            <Text className="font-sans text-body text-fg-default">{bgmOn ? ko.menu.soundOff : ko.menu.soundOn}</Text>
          </Pressable>
        </Surface>
      )}
    </View>
  );
}
