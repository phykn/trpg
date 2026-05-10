import React from 'react';
import { PanResponder, View } from 'react-native';

import { Chip, Surface } from '@/components/ui';
import {
  MiniMapPanel,
  type StoryGraphModel,
  type Place,
} from '@/logic/story-graph';

import type { PanelAction, PanelSlot } from '@/logic/info-panel/types';

import { PanelBody } from '@/components/info-panel/PanelBody';

const FLOAT_BUFFER = 540;

export function ContextCard({ slots, miniMapGraph, place, activeId, onSelect, onAction }: {
  slots: PanelSlot[];
  miniMapGraph: StoryGraphModel;
  place: Place | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onAction?: (action: PanelAction) => void;
}) {
  const activeSlot = slots.find((s) => s.id === activeId) ?? null;
  const panel = activeSlot?.panel ?? null;
  const miniMapOpen = activeId === 'map';
  const [chipBarHeight, setChipBarHeight] = React.useState(48);
  const floating = panel || miniMapOpen;

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
        className="flex-row p-2 gap-2 items-center"
      >
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
    </View>
  );
}
