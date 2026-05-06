import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors, toneColor } from '@/design/tokens';
import { ExpandableTitle, ExpandGroup, LabeledRow, Row, SEP } from '@/components/ui';
import type { PanelAction } from '@/logic/info-panel';

import type { StoryGraphEdge, StoryGraphModel } from './types';
import { StoryGraphCanvas } from './StoryGraphCanvas';
import { actionForNode } from './_nodeActions';

type PlaceState = 'current' | 'reachable' | 'unreachable';

const PLACE_LEGEND: { state: PlaceState; label: string; color: string }[] = [
  { state: 'current', label: '현재 위치', color: colors.accent.fg },
  { state: 'reachable', label: '갈 수 있는 곳', color: colors.success.fg },
  { state: 'unreachable', label: '갈 수 없는 곳', color: colors.fg.subtle },
];

export function MapPanel({
  graph,
  framed = false,
  accessibilityLabel = '현재 스토리 그래프',
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
  unseenNodeIds,
  onNodeSeen,
}: {
  graph: StoryGraphModel;
  framed?: boolean;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
  unseenNodeIds?: Set<string>;
  onNodeSeen?: (id: string) => void;
}) {
  const placeStates = React.useMemo<Record<string, PlaceState>>(() => {
    return Object.fromEntries(
      graph.nodes
        .filter((n) => n.kind === 'place' || n.kind === 'location')
        .map((n) => {
          const state: PlaceState =
            n.kind === 'place'
              ? 'current'
              : n.reachable
                ? 'reachable'
                : 'unreachable';
          return [n.id, state];
        }),
    );
  }, [graph]);

  const visibleGraph: StoryGraphModel = React.useMemo(() => {
    const placeNodes = graph.nodes.filter((n) => n.kind === 'place' || n.kind === 'location');
    const placeIds = new Set(placeNodes.map((n) => n.id));
    const seenPair = new Set<string>();
    const placeEdges: StoryGraphEdge[] = [];
    for (const e of graph.edges) {
      if (e.kind !== 'move') continue;
      if (!placeIds.has(e.source) || !placeIds.has(e.target)) continue;
      const pair = e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`;
      if (seenPair.has(pair)) continue;
      seenPair.add(pair);
      placeEdges.push(e);
    }
    const currentPlace = placeNodes.find((n) => n.kind === 'place');
    const reachableCount = placeNodes.filter(
      (n) => n.kind === 'location' && placeStates[n.id] === 'reachable',
    ).length;
    const summary = [
      currentPlace ? `현재 ${currentPlace.label}` : null,
      `장소 ${placeNodes.length}곳`,
      `이동 가능 ${reachableCount}`,
    ]
      .filter(Boolean)
      .join(SEP);
    return { nodes: placeNodes, edges: placeEdges, summary };
  }, [graph, placeStates]);

  const currentPlaceId = React.useMemo(
    () => visibleGraph.nodes.find((n) => n.kind === 'place')?.id ?? undefined,
    [visibleGraph.nodes],
  );

  const selectedNode = visibleGraph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedAction = selectedNode ? actionForNode(selectedNode) : null;
  const placeFeatures = (() => {
    if (!selectedNode) return null;
    if (!('risk' in selectedNode) || !selectedNode.risk) return null;
    return { risk: selectedNode.risk };
  })();
  const placeDescription = (() => {
    if (!selectedNode) return '';
    if (!('description' in selectedNode)) return '';
    return selectedNode.description || '';
  })();
  const metaText = (() => {
    if (!selectedNode) return '';
    if (selectedNode.kind === 'place') return '현재 위치';
    if (selectedNode.kind === 'location' && !selectedAction) return '이동 불가';
    return '';
  })();

  return (
    <View>
      {!framed && (
        <View
          className="px-4 pt-3 flex-row items-center"
          style={{ minHeight: 22 }}
        >
          <ExpandableTitle text="지도" />
        </View>
      )}
      <View
        accessibilityLabel={`${accessibilityLabel}. ${visibleGraph.summary}`}
        className={`${framed ? 'border border-border-default rounded-md bg-canvas-subtle px-3 py-3' : 'px-4 pt-2 pb-3'} gap-2`}
      >
        <View style={{ aspectRatio: 1.618 }}>
          <StoryGraphCanvas
            graph={visibleGraph}
            accessibilityLabel={accessibilityLabel}
            selectedNodeId={selectedNodeId}
            onNodeSelect={(id) => {
              if (id) onNodeSeen?.(id);
              onNodeSelect?.(id);
            }}
            unseenNodeIds={unseenNodeIds}
            centerNodeId={currentPlaceId}
          />
        </View>

        {selectedNode ? (
          <View className="border-t border-border-default pt-2.5 gap-2">
            <View className="gap-2.5">
              <View
                className="flex-row items-center gap-3"
                style={{ minHeight: 22 }}
              >
                <ExpandableTitle text={selectedNode.label} />
                {selectedAction && onAction ? (
                  <Pressable
                    onPress={() => onAction(selectedAction)}
                    disabled={actionDisabled}
                    accessibilityRole="button"
                    accessibilityLabel={`${selectedNode.label} ${selectedAction.label}`}
                    className={`rounded-full px-3.5 py-1 ${actionDisabled ? 'bg-accent-muted opacity-60' : 'bg-accent-muted active:opacity-80'}`}
                  >
                    <Text className="font-sans-semibold text-caption text-accent-fg">
                      {actionDisabled ? '처리 중' : selectedAction.label}
                    </Text>
                  </Pressable>
                ) : metaText ? (
                  <Text
                    numberOfLines={1}
                    className="font-sans text-caption italic text-fg-muted"
                  >
                    {metaText}
                  </Text>
                ) : null}
              </View>
              {placeFeatures ? (
                <Row label="환경">
                  <Text
                    numberOfLines={1}
                    className="font-sans text-panel text-fg-default"
                  >
                    <Text
                      className="font-sans-semibold"
                      style={{ color: toneColor[placeFeatures.risk.tone] }}
                    >
                      {placeFeatures.risk.label}
                    </Text>
                  </Text>
                </Row>
              ) : null}
              <ExpandGroup>
                {placeDescription ? (
                  <LabeledRow label="모습">
                    {placeDescription}
                  </LabeledRow>
                ) : null}
              </ExpandGroup>
            </View>
          </View>
        ) : null}
      </View>
    </View>
  );
}
