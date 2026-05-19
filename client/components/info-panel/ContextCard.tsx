import React from 'react';
import { PanResponder, ScrollView, View } from 'react-native';

import { Chip, Surface } from '@/components/ui';
import {
  MiniMapPanel,
  type StoryGraphModel,
  type Place,
} from '@/logic/story-graph';

import type { PanelAction, PanelSlot } from '@/logic/info-panel/types';

import { PanelBody } from '@/components/info-panel/PanelBody';

const CONTEXT_PANEL_MAX_HEIGHT = 340;

export function ContextCard({ slots, miniMapGraph, place, activeId, onSelect, onAction, actionDisabled = false, leading, trailing }: {
  slots: PanelSlot[];
  miniMapGraph: StoryGraphModel;
  place: Place | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  const activeSlot = slots.find((s) => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;
  const miniMapOpen = activeId === 'map';

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
      style={{ zIndex: 10 }}
    >
      <View
        className="flex-row gap-2 items-center"
      >
        {leading}
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
        {trailing}
      </View>
      {panel && (
        <Surface
          variant="floating"
          className="mt-1 overflow-hidden"
          style={{ maxHeight: CONTEXT_PANEL_MAX_HEIGHT }}
          {...panResponder.panHandlers}
        >
          <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            <PanelBody
              panel={panel}
              onAction={onAction}
              actionDisabled={actionDisabled}
            />
          </ScrollView>
        </Surface>
      )}
      {miniMapOpen && (
        <Surface
          variant="floating"
          className="mt-1 overflow-hidden"
          style={{ maxHeight: CONTEXT_PANEL_MAX_HEIGHT }}
          {...panResponder.panHandlers}
        >
          <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            <MiniMapPanel
              graph={miniMapGraph}
              place={place}
              onAction={onAction}
              actionDisabled={actionDisabled}
            />
          </ScrollView>
        </Surface>
      )}
    </View>
  );
}
