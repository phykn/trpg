import React from 'react';
import { Pressable, Text, View } from 'react-native';

import type { StoryGraphModel } from '@/presenters/storyGraph';
import type { PanelAction } from '@/types/ui';

import { StoryGraphPanel } from './StoryGraphPanel';

export function MiniMapPanel({
  graph,
  onOpenFullMap,
  onAction,
}: {
  graph: StoryGraphModel;
  onOpenFullMap: () => void;
  onAction?: (action: PanelAction) => void;
}) {
  const [selectedNodeId, setSelectedNodeId] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (selectedNodeId && !graph.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(null);
    }
  }, [graph.nodes, selectedNodeId]);

  return (
    <View className="gap-1">
      <StoryGraphPanel
        graph={graph}
        canvasHeight={210}
        title="지도"
        accessibilityLabel="미니맵"
        selectedNodeId={selectedNodeId}
        onNodeSelect={setSelectedNodeId}
        onAction={onAction}
      />
      <View className="border-t border-border-default px-3 py-2">
        <Pressable
          onPress={onOpenFullMap}
          accessibilityRole="button"
          accessibilityLabel="전체 지도 열기"
          className="self-start rounded-sm border border-border-default bg-canvas-default px-3 py-1.5 active:bg-canvas-inset"
        >
          <Text className="font-sans text-panel text-fg-default">전체 지도</Text>
        </Pressable>
      </View>
    </View>
  );
}
