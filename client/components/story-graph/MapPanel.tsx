import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { toneColor } from '@/design/tokens';
import { ExpandableTitle, ExpandGroup, LabeledRow, Row } from '@/components/ui';
import { ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import { buildPlaceMapGraph, currentPlaceId } from '@/logic/story-graph/presenters';
import type { StoryGraphModel } from '@/logic/story-graph/types';
import { StoryGraphCanvas } from './StoryGraphCanvas';
import { actionsForNode } from '@/logic/story-graph/_nodeActions';

export function MapPanel({
  graph,
  framed = false,
  accessibilityLabel = ko.panel.storyGraph,
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
  unseenNodeIds,
  onNodeSeen,
  showSelectedDetails = true,
  frameTopBorder = true,
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
  showSelectedDetails?: boolean;
  frameTopBorder?: boolean;
}) {
  const visibleGraph = React.useMemo(() => buildPlaceMapGraph(graph), [graph]);
  const centerNodeId = React.useMemo(() => currentPlaceId(visibleGraph), [visibleGraph]);

  const selectedNode = visibleGraph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedActions = selectedNode ? actionsForNode(selectedNode) : [];
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
    if (selectedNode.kind === 'place') return ko.panel.here;
    if (selectedNode.kind === 'location' && selectedActions.length === 0) return ko.status.moveBlocked;
    return '';
  })();

  const framedClass = frameTopBorder
    ? 'border border-border-default'
    : 'border-l border-r border-b border-border-default';

  return (
    <View>
      {!framed && (
        <View
          className="px-4 pt-3 flex-row items-center"
          style={{ minHeight: 22 }}
        >
          <ExpandableTitle text={ko.panel.map} />
        </View>
      )}
      <View
        accessibilityLabel={`${accessibilityLabel}. ${visibleGraph.summary}`}
        className={`${framed ? `${framedClass} rounded-sm bg-canvas-inset px-3 py-3` : 'px-4 pt-2 pb-3'} gap-2`}
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
            centerNodeId={centerNodeId}
          />
        </View>

        {showSelectedDetails && selectedNode ? (
          <View className="border-t border-border-default pt-2.5 gap-2">
            <View className="gap-2.5">
              <View
                className="flex-row items-center gap-3"
                style={{ minHeight: 22 }}
              >
                <ExpandableTitle text={selectedNode.label} />
                {selectedActions.length > 0 && onAction ? (
                  <View className="flex-row flex-wrap items-center gap-1.5">
                    {selectedActions.map((action) => (
                      <Pressable
                        key={`${action.kind}:${action.label}`}
                        onPress={() => onAction(action)}
                        disabled={actionDisabled}
                        accessibilityRole="button"
                        accessibilityLabel={`${selectedNode.label} ${action.label}`}
                        className={`rounded-sm border border-accent-fg px-3 py-1 ${actionDisabled ? 'bg-accent-muted opacity-60' : 'bg-accent-muted active:opacity-80'}`}
                      >
                        <Text className="font-sans-semibold text-caption text-accent-fg">
                          {actionDisabled ? ko.status.busy : action.label}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
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
                <Row label={ko.panel.environment}>
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
                  <LabeledRow label={ko.panel.appearance}>
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
