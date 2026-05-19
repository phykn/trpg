import React from 'react';
import { Text, View } from 'react-native';

import { compose, ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import { currentPlaceId as getCurrentPlaceId, resolvePlaceSelection } from '@/logic/story-graph/presenters';
import type { Place, StoryGraphModel } from '@/logic/story-graph/types';

import { MapPanel } from './MapPanel';

export function MiniMapPanel({
  graph,
  place,
  onAction,
  actionDisabled = false,
}: {
  graph: StoryGraphModel;
  place: Place | null;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
}) {
  const currentPlaceId = React.useMemo(
    () => getCurrentPlaceId(graph) ?? null,
    [graph],
  );
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(currentPlaceId);
  const previousCurrentPlaceId = React.useRef<string | null>(currentPlaceId);

  React.useEffect(() => {
    const nextSelectedNodeId = resolvePlaceSelection({
      selectedNodeId,
      previousCurrentPlaceId: previousCurrentPlaceId.current,
      nextCurrentPlaceId: currentPlaceId,
      nextNodeIds: new Set(graph.nodes.map((node) => node.id)),
    });
    previousCurrentPlaceId.current = currentPlaceId;
    if (nextSelectedNodeId !== selectedNodeId) {
      setSelectedNodeId(nextSelectedNodeId);
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
        actionDisabled={actionDisabled}
        framed
        showSelectedDetails={false}
        frameTopBorder={false}
      />
    </View>
  );
}
