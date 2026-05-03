import React from 'react';
import { type GestureResponderHandlers, PanResponder, Pressable, Text, View } from 'react-native';

import { shadow } from '@/design/tokens';
import { Surface } from '@/components/ui';
import {
  MiniMapPanel,
  StoryGraphScreen,
  type StoryGraphModel,
} from '@/features/story-graph';
import type { Place } from '@/types/domain';
import type { PanelAction, PanelSlot } from '@/types/ui';

import { ChipTab } from './ChipTab';
import { IconButton, ICON_PATH } from './IconButton';
import { PanelBody } from './PanelBody';

const FLOAT_BUFFER = 540;

function FloatingDock({ top, panHandlers, children }: {
  top: number;
  panHandlers: GestureResponderHandlers;
  children: React.ReactNode;
}) {
  return (
    <View
      className="bg-canvas-subtle border border-border-default rounded-md overflow-hidden"
      style={{
        position: 'absolute',
        top,
        left: 0,
        right: 0,
        maxHeight: FLOAT_BUFFER,
        ...shadow.floating,
      }}
      {...panHandlers}
    >
      {children}
    </View>
  );
}

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
          d={ICON_PATH.map}
          label="전체 지도"
          active={graphOpen}
          onPress={() => onSelect('graph')}
        />
      </Surface>
      {panel && (
        <FloatingDock top={chipBarHeight + 4} panHandlers={panResponder.panHandlers}>
          <PanelBody panel={panel} onAction={onAction} />
        </FloatingDock>
      )}
      {miniMapOpen && (
        <FloatingDock top={chipBarHeight + 4} panHandlers={panResponder.panHandlers}>
          <MiniMapPanel
            graph={miniMapGraph}
            place={place}
            onAction={onAction}
          />
        </FloatingDock>
      )}
      {graphOpen && (
        <FloatingDock top={chipBarHeight + 4} panHandlers={panResponder.panHandlers}>
          <StoryGraphScreen
            onAction={(action) => {
              onSelect('graph');
              onAction?.(action);
            }}
          />
        </FloatingDock>
      )}
      {menuOpen && (
        <View
          className="bg-canvas-subtle border border-border-default rounded-md overflow-hidden"
          style={{
            position: 'absolute',
            top: chipBarHeight + 4,
            left: 0,
            minWidth: 112,
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
            accessibilityLabel="새로운 이야기"
            className="px-3 py-2"
          >
            <Text className="font-sans text-body text-fg-default">새로운 이야기</Text>
          </Pressable>
          <Pressable
            onPress={() => {
              onMenuClose();
              onBgmToggle();
            }}
            accessibilityRole="button"
            accessibilityLabel={bgmOn ? '소리 끄기' : '소리 켜기'}
            className="px-3 py-2"
          >
            <Text className="font-sans text-body text-fg-default">{bgmOn ? '소리 끄기' : '소리 켜기'}</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
