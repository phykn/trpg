import React from 'react';
import { Text, View } from 'react-native';

import { SEP } from '@/components/ui';
import { toneColor } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import type { Place, StoryGraphModel } from '@/logic/story-graph/types';

import { MapPanel } from './MapPanel';

export function MiniMapPanel({
  graph,
  place,
  onAction,
}: {
  graph: StoryGraphModel;
  place: Place | null;
  onAction?: (action: PanelAction) => void;
}) {
  const currentPlaceId = React.useMemo(
    () => graph.nodes.find((n) => n.kind === 'place')?.id ?? null,
    [graph.nodes],
  );
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(currentPlaceId);

  React.useEffect(() => {
    if (!selectedNodeId || !graph.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(currentPlaceId);
    }
  }, [graph.nodes, selectedNodeId, currentPlaceId]);

  const dayWeather = place
    ? [place.dayPhase, ...place.weather].filter(Boolean).join(SEP)
    : '';

  return (
    <View>
      {place ? (
        <View
          className="px-4 pt-3 flex-row items-center gap-2"
          style={{ minHeight: 22 }}
        >
          <View className="flex-1 min-w-0">
            <Text
              numberOfLines={1}
              className="font-serif-medium text-title text-fg-default"
            >
              {place.name}
            </Text>
          </View>
          <View className="flex-1 min-w-0">
            <Text
              numberOfLines={1}
              className="font-sans text-caption italic text-right text-fg-muted"
            >
              {dayWeather ? `${dayWeather}${SEP}` : ''}
              <Text
                className="font-sans-semibold"
                style={{ color: toneColor[place.risk.tone] }}
              >
                {place.risk.label}
              </Text>
            </Text>
          </View>
        </View>
      ) : null}
      <MapPanel
        graph={graph}
        accessibilityLabel={ko.panel.miniMap}
        selectedNodeId={selectedNodeId}
        onNodeSelect={setSelectedNodeId}
        onAction={onAction}
      />
    </View>
  );
}
