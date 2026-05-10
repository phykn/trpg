import React from 'react';
import { Text, View, type LayoutChangeEvent, type ViewStyle } from 'react-native';
import Svg, { Circle, G, Line, Text as SvgText } from 'react-native-svg';

import { colors, fontFamily } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { layoutNativeStoryGraph, type NativeStoryGraphLayoutNode } from '@/logic/story-graph/nativeLayout';
import type { StoryGraphModel } from '@/logic/story-graph/types';

export function StoryGraphCanvas({
  graph,
  height,
  accessibilityLabel = ko.panel.storyGraph,
  selectedNodeId = null,
  onNodeSelect,
  unseenNodeIds,
  centerNodeId,
}: {
  graph: StoryGraphModel;
  height?: number;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  unseenNodeIds?: Set<string>;
  centerNodeId?: string;
}) {
  const [size, setSize] = React.useState({ width: 0, height: height ?? 0 });

  const onLayout = React.useCallback((event: LayoutChangeEvent) => {
    const nextWidth = Math.round(event.nativeEvent.layout.width);
    const nextHeight = Math.round(event.nativeEvent.layout.height);
    setSize((current) => {
      if (current.width === nextWidth && current.height === nextHeight) return current;
      return { width: nextWidth, height: nextHeight };
    });
  }, []);

  const layout = React.useMemo(() => {
    if (size.width <= 0 || size.height <= 0) return null;
    return layoutNativeStoryGraph(graph, {
      width: size.width,
      height: size.height,
      centerNodeId,
      selectedNodeId,
    });
  }, [centerNodeId, graph, selectedNodeId, size.height, size.width]);

  const containerStyle = React.useMemo<ViewStyle[]>(
    () => [{ minHeight: height ?? 160 }, height ? { height } : { flex: 1 }],
    [height],
  );

  return (
    <View
      onLayout={onLayout}
      accessibilityLabel={`${accessibilityLabel}. ${graph.summary}`}
      className="flex-1 overflow-hidden rounded-md border border-border-default bg-canvas-inset"
      style={containerStyle}
    >
      {layout && graph.nodes.length > 0 ? (
        <Svg width={size.width} height={size.height}>
          {layout.edges.map((edge) => (
            <Line
              key={edge.id}
              x1={edge.x1}
              y1={edge.y1}
              x2={edge.x2}
              y2={edge.y2}
              stroke={colors.border.strong}
              strokeLinecap="round"
              strokeWidth={1.25}
            />
          ))}
          {layout.nodes.map((node) => (
            <G
              key={node.id}
              onPress={onNodeSelect ? () => onNodeSelect(node.id) : undefined}
            >
              <Circle
                cx={node.x}
                cy={node.y}
                r={21}
                fill="transparent"
              />
              {node.selected ? (
                <Circle
                  cx={node.x}
                  cy={node.y}
                  r={15}
                  fill="transparent"
                  stroke={colors.accent.fg}
                  strokeWidth={1.5}
                />
              ) : null}
              <Circle
                cx={node.x}
                cy={node.y}
                r={10}
                fill={fillForNode(node)}
                opacity={node.reachable || node.current ? 1 : 0.42}
                stroke={strokeForNode(node)}
                strokeWidth={node.current ? 2 : 1}
              />
              {unseenNodeIds?.has(node.id) ? (
                <Circle
                  cx={node.x + 11}
                  cy={node.y - 11}
                  r={3}
                  fill={colors.accent.fg}
                />
              ) : null}
              <SvgText
                x={node.x}
                y={node.y + 29}
                fill={node.current || node.selected ? colors.fg.default : colors.fg.muted}
                fontFamily={fontFamily.sans[0]}
                fontSize={11}
                textAnchor="middle"
              >
                {truncateLabel(node.label)}
              </SvgText>
            </G>
          ))}
        </Svg>
      ) : (
        <View className="flex-1 items-center justify-center px-3">
          <Text className="font-sans text-panel text-fg-muted">{ko.empty.panel}</Text>
        </View>
      )}
    </View>
  );
}

function fillForNode(node: NativeStoryGraphLayoutNode): string {
  if (node.current) return colors.exp.fg;
  if (!node.reachable) return colors.canvas.floating;
  if (node.kind === 'quest') return colors.danger.fg;
  if (node.kind === 'subject' || node.kind === 'target' || node.kind === 'hero') {
    return colors.success.fg;
  }
  return colors.accent.fg;
}

function strokeForNode(node: NativeStoryGraphLayoutNode): string {
  if (node.selected) return colors.accent.fg;
  if (node.current) return colors.exp.fg;
  if (!node.reachable) return colors.fg.subtle;
  return colors.border.strong;
}

function truncateLabel(label: string): string {
  if (label.length <= 8) return label;
  return `${label.slice(0, 7)}...`;
}
