import { Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { StoryGraphModel } from '@/logic/story-graph/types';

export function StoryGraphCanvas({
  graph,
  accessibilityLabel = ko.panel.storyGraph,
  selectedNodeId = null,
  onNodeSelect,
}: {
  graph: StoryGraphModel;
  height?: number;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  unseenNodeIds?: Set<string>;
  centerNodeId?: string;
}) {
  return (
    <View accessibilityLabel={`${accessibilityLabel}. ${graph.summary}`} className="gap-1.5">
      {graph.nodes.slice(0, 8).map((node) => (
        <Pressable
          key={node.id}
          onPress={() => onNodeSelect?.(node.id)}
          accessibilityRole={onNodeSelect ? 'button' : undefined}
          accessibilityLabel={node.label}
          className={`flex-row items-center gap-2 rounded-sm px-1 py-0.5 ${selectedNodeId === node.id ? 'bg-accent-muted' : ''}`}
        >
          <Text className="font-mono text-meta text-fg-subtle">{node.kind}</Text>
          <Text numberOfLines={1} className="flex-1 font-sans text-panel text-fg-default">
            {node.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}
