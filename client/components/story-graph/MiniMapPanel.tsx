import React from 'react';
import { Text, View } from 'react-native';

import { compose, ko } from '@/locale/ko';
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
              {compose.neighborhoodMap(place.name)}
            </Text>
          </View>
          <View className="flex-1 min-w-0">
            <Text
              numberOfLines={1}
              className="font-sans text-caption text-right text-fg-muted"
            >
              {compose.currentLocation(place.name)}
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
        framed
        showSelectedDetails={false}
        frameTopBorder={false}
      />
    </View>
  );
}
