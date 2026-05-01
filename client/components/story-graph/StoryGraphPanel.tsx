import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import type {
  StoryGraphEdge,
  StoryGraphModel,
  StoryGraphNode,
  StoryGraphNodeKind,
} from '@/presenters/storyGraph';
import type { PanelAction } from '@/types/ui';

import { StoryGraphCanvas } from './StoryGraphCanvas';

const LEGEND: { kind: StoryGraphNodeKind; label: string; color: string }[] = [
  { kind: 'hero', label: '주인공', color: colors.accent.fg },
  { kind: 'place', label: '위치', color: colors.exp.fg },
  { kind: 'location', label: '배경', color: colors.border.default },
  { kind: 'subject', label: '대상', color: '#567A8F' },
  { kind: 'quest', label: '퀘스트', color: colors.danger.fg },
  { kind: 'target', label: '인물', color: colors.success.fg },
];

const KIND_LABEL: Record<StoryGraphNodeKind, string> = {
  hero: '주인공',
  place: '현재 위치',
  location: '배경',
  subject: '대상',
  quest: '퀘스트',
  target: '등장인물',
};

function moveIntent(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return `${name}로 이동`;
  const final = (last - 0xac00) % 28;
  if (final === 0 || final === 8) return `${name}로 이동`;
  return `${name}으로 이동`;
}

function isReachableFromCurrentPlace(node: StoryGraphNode, graph: StoryGraphModel): boolean {
  const currentPlace = graph.nodes.find((item) => item.kind === 'place');
  if (!currentPlace) return false;
  if (node.kind === 'location') {
    return graph.edges.some((edge) =>
      edge.source === currentPlace.id && edge.target === node.id && edge.label === '이동',
    );
  }
  if (node.kind === 'subject' || node.kind === 'target') {
    return graph.edges.some((edge) =>
      edge.source === node.id
      && edge.target === currentPlace.id
      && (edge.label === '등장' || edge.label === '같은 장소'),
    );
  }
  return false;
}

function actionForNode(node: StoryGraphNode, graph: StoryGraphModel): PanelAction | null {
  if (!isReachableFromCurrentPlace(node, graph)) return null;
  if (node.kind === 'location') {
    return { label: '이동', intent: moveIntent(node.label) };
  }
  if (node.kind === 'subject' || node.kind === 'target') {
    return { label: '이동', intent: `${node.label}에게 이동` };
  }
  return null;
}

function relationLabel(edge: StoryGraphEdge, node: StoryGraphNode, graph: StoryGraphModel): string {
  const otherId = edge.source === node.id ? edge.target : edge.source;
  const other = graph.nodes.find((item) => item.id === otherId);
  return other ? `${edge.label} · ${other.label}` : edge.label;
}

export function StoryGraphPanel({
  graph,
  canvasHeight = 260,
  framed = false,
  sourceLabel,
  title = '스토리 그래프',
  accessibilityLabel = '현재 스토리 그래프',
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
}: {
  graph: StoryGraphModel;
  canvasHeight?: number;
  framed?: boolean;
  sourceLabel?: string;
  title?: string;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
}) {
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const relatedEdges = selectedNode
    ? graph.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
    : [];
  const selectedAction = selectedNode ? actionForNode(selectedNode, graph) : null;

  return (
    <View
      accessibilityLabel={`${accessibilityLabel}. ${graph.summary}`}
      className={`${framed ? 'border border-border-default rounded-md bg-canvas-subtle px-3 py-3' : 'px-3 py-3'} gap-2.5`}
    >
      <View className="flex-row items-start gap-3">
        <View className="flex-1 min-w-0">
          <Text className="font-sans-semibold text-body text-fg-default">{title}</Text>
          <Text numberOfLines={2} className="font-sans text-caption text-fg-muted">
            {graph.summary}
          </Text>
        </View>
        <Text className="font-mono text-meta text-fg-subtle">
          {sourceLabel ? `${sourceLabel} · ` : ''}{graph.nodes.length}N/{graph.edges.length}E
        </Text>
      </View>

      <StoryGraphCanvas
        graph={graph}
        height={canvasHeight}
        accessibilityLabel={accessibilityLabel}
        selectedNodeId={selectedNodeId}
        onNodeSelect={onNodeSelect}
      />

      <View className="flex-row flex-wrap gap-x-3 gap-y-1">
        {LEGEND.map((item) => (
          <View key={item.kind} className="flex-row items-center gap-1">
            <View
              style={{
                width: 7,
                height: 7,
                borderRadius: 4,
                backgroundColor: item.color,
              }}
            />
            <Text className="font-sans text-caption text-fg-muted">{item.label}</Text>
          </View>
        ))}
      </View>

      {selectedNode ? (
        <View className="border-t border-border-default pt-2.5 gap-2">
          <View className="flex-row items-start gap-3">
            <View className="flex-1 min-w-0">
              <Text className="font-sans text-meta text-fg-subtle">{KIND_LABEL[selectedNode.kind]}</Text>
              <Text numberOfLines={1} className="font-serif-medium text-title text-fg-default">
                {selectedNode.label}
              </Text>
              <Text numberOfLines={2} className="font-sans text-caption text-fg-muted">
                {selectedNode.detail}
              </Text>
            </View>
            {selectedAction && onAction ? (
              <Pressable
                onPress={() => onAction(selectedAction)}
                disabled={actionDisabled}
                accessibilityRole="button"
                accessibilityLabel={`${selectedNode.label} 이동`}
                className={`rounded-sm border border-border-default px-3 py-1.5 ${actionDisabled ? 'bg-canvas-inset opacity-60' : 'bg-canvas-default active:bg-canvas-inset'}`}
              >
                <Text className="font-sans-semibold text-panel text-fg-default">
                  {actionDisabled ? '처리 중' : selectedAction.label}
                </Text>
              </Pressable>
            ) : selectedNode.kind === 'location' || selectedNode.kind === 'subject' || selectedNode.kind === 'target' ? (
              <Text className="font-sans text-caption text-fg-subtle">현재 위치에서 바로 이동할 수 없습니다.</Text>
            ) : null}
          </View>
          {relatedEdges.length > 0 ? (
            <View className="flex-row flex-wrap gap-1.5">
              {relatedEdges.slice(0, 5).map((edge) => (
                <View
                  key={edge.id}
                  className="rounded-sm border border-border-default bg-canvas-default px-2 py-1"
                >
                  <Text numberOfLines={1} className="font-sans text-caption text-fg-muted">
                    {relationLabel(edge, selectedNode, graph)}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
