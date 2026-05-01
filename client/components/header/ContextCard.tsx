import React from 'react';
import { PanResponder, Pressable, Text, View } from 'react-native';

import { shadow } from '@/design/tokens';
import type { StoryGraphModel } from '@/presenters/storyGraph';
import type { PanelAction, PanelSlot } from '@/types/ui';

import { MiniMapPanel } from '../story-graph';
import { ChipTab } from './ChipTab';
import { IconButton, ICON_PATH } from './IconButton';
import { PanelBody } from './PanelBody';

const FLOAT_BUFFER = 480;

export function ContextCard({ slots, miniMapGraph, activeId, menuOpen, bgmOn, onSelect, onMenuToggle, onMenuClose, onBgmToggle, onNewGame, onGraph, onAction }: {
  slots: PanelSlot[];
  miniMapGraph: StoryGraphModel;
  activeId: string | null;
  menuOpen: boolean;
  bgmOn: boolean;
  onSelect: (id: string) => void;
  onMenuToggle: () => void;
  onMenuClose: () => void;
  onBgmToggle: () => void;
  onNewGame?: () => void;
  onGraph?: () => void;
  onAction?: (action: PanelAction) => void;
}) {
  const activeSlot = slots.find((s) => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;
  const miniMapOpen = activeId === 'map';
  const [chipBarHeight, setChipBarHeight] = React.useState(48);
  const floating = panel || miniMapOpen || menuOpen;

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
      <View
        onLayout={(e) => setChipBarHeight(e.nativeEvent.layout.height)}
        className="bg-canvas-subtle border border-border-default rounded-md flex-row p-2 gap-1 items-center"
        style={shadow.paper}
      >
        <IconButton d={ICON_PATH.menu} label="메뉴" onPress={onMenuToggle} />
        <View className="flex-1 flex-row gap-1">
          {slots.map((s) => (
            <ChipTab
              key={s.id}
              chip={s.chip}
              active={s.id === activeId}
              onPress={() => onSelect(s.id)}
            />
          ))}
        </View>
        <IconButton
          d={bgmOn ? ICON_PATH.volumeOn : ICON_PATH.volumeOff}
          label={bgmOn ? '배경음 끄기' : '배경음 켜기'}
          onPress={onBgmToggle}
        />
      </View>
      {panel && (
        <View
          className="bg-canvas-subtle border border-border-default rounded-md overflow-hidden"
          style={{
            position: 'absolute',
            top: chipBarHeight + 4,
            left: 0,
            right: 0,
            maxHeight: FLOAT_BUFFER,
            ...shadow.floating,
          }}
          {...panResponder.panHandlers}
        >
          <PanelBody panel={panel} kind={activeSlot?.id} onAction={onAction} />
        </View>
      )}
      {miniMapOpen && (
        <View
          className="bg-canvas-subtle border border-border-default rounded-md overflow-hidden"
          style={{
            position: 'absolute',
            top: chipBarHeight + 4,
            left: 0,
            right: 0,
            maxHeight: FLOAT_BUFFER,
            ...shadow.floating,
          }}
          {...panResponder.panHandlers}
        >
          <MiniMapPanel
            graph={miniMapGraph}
            onOpenFullMap={onGraph ?? (() => {})}
            onAction={onAction}
          />
        </View>
      )}
      {menuOpen && (
        <View
          className="bg-canvas-subtle border border-border-default rounded-md"
          style={{
            position: 'absolute',
            top: chipBarHeight + 4,
            left: 0,
            right: 0,
            maxHeight: FLOAT_BUFFER,
            zIndex: 20,
            ...shadow.floating,
          }}
        >
          <Pressable
            onPress={() => {
              onMenuClose();
              onNewGame?.();
            }}
            accessibilityRole="button"
            accessibilityLabel="새 게임"
            className="px-3 py-2.5"
          >
            <Text className="font-sans text-body text-fg-default">새 게임</Text>
          </Pressable>
          <View className="border-t border-border-default" />
          <Pressable
            onPress={() => {
              onMenuClose();
              onGraph?.();
            }}
            accessibilityRole="button"
            accessibilityLabel="전체 지도"
            className="px-3 py-2.5"
          >
            <Text className="font-sans text-body text-fg-default">전체 지도</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
