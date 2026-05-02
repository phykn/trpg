import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors, toneColor } from '@/design/tokens';
import {
  KIND_LABEL,
  type StoryGraphEdge,
  type StoryGraphModel,
} from '@/presenters/storyGraph';
import { SEP } from '@/presenters/format';
import type { Place, RiskBadge } from '@/types/domain';
import type { PanelAction } from '@/types/ui';

import { Expandable, ExpandableTitle } from '../ui';
import { StoryGraphCanvas } from './StoryGraphCanvas';
import { actionForNode } from './_nodeActions';

type PlaceState = 'current' | 'reachable' | 'unreachable';

const PLACE_LEGEND: { state: PlaceState; label: string; color: string }[] = [
  { state: 'current', label: '현재 위치', color: colors.accent.fg },
  { state: 'reachable', label: '갈 수 있는 곳', color: colors.success.fg },
  { state: 'unreachable', label: '갈 수 없는 곳', color: colors.fg.subtle },
];

const PLACE_STATE_SIZE: Record<PlaceState, number> = {
  current: 64,
  reachable: 52,
  unreachable: 44,
};

const PLACE_STATE_TIER: Record<PlaceState, number> = {
  current: 3,
  reachable: 2,
  unreachable: 1,
};

const PLACE_STATE_TEXT: Record<PlaceState, string> = {
  current: colors.fg['on-emphasis'],
  reachable: colors.fg.default,
  unreachable: colors.fg.default,
};

const DESCRIPTION_LINE_HEIGHT = 20;
const DESCRIPTION_CLAMP_LINES = 3;
const DESCRIPTION_CLASS = 'font-sans text-caption text-fg-muted';

function ExpandableDescription({ text }: { text: string }) {
  return (
    <Expandable
      contentKey={text}
      lineHeight={DESCRIPTION_LINE_HEIGHT}
      clampLines={DESCRIPTION_CLAMP_LINES}
      showHint
      textClassName={DESCRIPTION_CLASS}
      textStyle={{ lineHeight: DESCRIPTION_LINE_HEIGHT }}
      measureText={text}
    >
      {text}
    </Expandable>
  );
}

export function MapPanel({
  graph,
  canvasHeight = 260,
  framed = false,
  accessibilityLabel = '현재 스토리 그래프',
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
  place = null,
}: {
  graph: StoryGraphModel;
  canvasHeight?: number;
  framed?: boolean;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
  place?: Place | null;
}) {
  const placeStates = React.useMemo<Record<string, PlaceState>>(() => {
    return Object.fromEntries(
      graph.nodes
        .filter((n) => n.kind === 'place' || n.kind === 'location')
        .map((n) => {
          const state: PlaceState =
            n.status === 'current'
              ? 'current'
              : n.status === 'reachable_move'
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

  const nodeOverrides = React.useMemo(() => {
    const out: Record<string, { color: string; size: number; tier: number; textColor: string }> = {};
    for (const [id, state] of Object.entries(placeStates)) {
      const legend = PLACE_LEGEND.find((p) => p.state === state)!;
      out[id] = {
        color: legend.color,
        size: PLACE_STATE_SIZE[state],
        tier: PLACE_STATE_TIER[state],
        textColor: PLACE_STATE_TEXT[state],
      };
    }
    return out;
  }, [placeStates]);

  const selectedNode = visibleGraph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedAction = selectedNode ? actionForNode(selectedNode) : null;
  const selectedLabel = (() => {
    if (!selectedNode) return '';
    if (
      (selectedNode.kind === 'hero'
        || selectedNode.kind === 'subject'
        || selectedNode.kind === 'target')
      && selectedNode.alive === false
    ) {
      return `${selectedNode.label} (죽음)`;
    }
    return selectedNode.label;
  })();
  const selectedPlaceState: PlaceState | null = selectedNode
    ? placeStates[selectedNode.id] ?? null
    : null;
  const selectedPlaceLabel = selectedPlaceState
    ? PLACE_LEGEND.find((p) => p.state === selectedPlaceState)?.label ?? null
    : null;
  const selectedDescription: string | null = (() => {
    if (!selectedNode || !place) return null;
    if (selectedPlaceState === 'current') return place.description || null;
    if (selectedPlaceState === 'reachable') {
      const s = place.surroundings.find((s) => s.name === selectedNode.label);
      return s?.blurb || null;
    }
    return null;
  })();
  const selectedRisk: RiskBadge | null = (() => {
    if (!selectedNode || !place) return null;
    let r: RiskBadge | null = null;
    if (selectedPlaceState === 'current') r = place.risk;
    else if (selectedPlaceState === 'reachable') {
      const s = place.surroundings.find((s) => s.name === selectedNode.label);
      r = s?.risk ?? null;
    }
    if (!r || r.tone === 'neutral') return null;
    return r;
  })();
  const selectedEnvMeta: string | null = (() => {
    if (!selectedNode || !place) return null;
    if (selectedPlaceState !== 'current') return null;
    return [place.dayPhase, ...place.weather].filter(Boolean).join(SEP) || null;
  })();

  return (
    <View
      accessibilityLabel={`${accessibilityLabel}. ${visibleGraph.summary}`}
      className={`${framed ? 'border border-border-default rounded-md bg-canvas-subtle px-3 py-3' : 'px-2 pt-2 pb-3'} gap-2`}
    >
      <StoryGraphCanvas
        graph={visibleGraph}
        height={canvasHeight}
        accessibilityLabel={accessibilityLabel}
        selectedNodeId={selectedNodeId}
        onNodeSelect={onNodeSelect}
        nodeOverrides={nodeOverrides}
        arrows={false}
        edgeLabels={false}
        layout="cose"
        boxNodes
        centerNodeId={visibleGraph.nodes.find((n) => n.kind === 'place')?.id}
        clearOnBackgroundTap={false}
      />

      {selectedNode ? (
        <View className="border-t border-border-default pt-2.5 gap-2">
          <View>
            <Text className="font-sans text-meta text-fg-subtle">
              {selectedPlaceLabel ?? KIND_LABEL[selectedNode.kind]}
              {selectedRisk ? (
                <Text
                  className="font-sans-semibold"
                  style={{ color: toneColor[selectedRisk.tone] }}
                >
                  {` (${selectedRisk.label})`}
                </Text>
              ) : null}
            </Text>
            <View className="mt-1 flex-row items-center justify-between gap-3">
              <ExpandableTitle
                text={selectedLabel}
                color={selectedRisk ? toneColor[selectedRisk.tone] : colors.fg.default}
              />
              {selectedAction && onAction ? (
                <Pressable
                  onPress={() => onAction(selectedAction)}
                  disabled={actionDisabled}
                  accessibilityRole="button"
                  accessibilityLabel={`${selectedNode.label} 이동`}
                  className={`rounded-full px-3.5 py-1 ${actionDisabled ? 'bg-accent-muted opacity-60' : 'bg-accent-muted active:opacity-80'}`}
                >
                  <Text className="font-sans-semibold text-caption text-accent-fg">
                    {actionDisabled ? '처리 중' : selectedAction.label}
                  </Text>
                </Pressable>
              ) : null}
            </View>
            {selectedEnvMeta ? (
              <Text className="mt-1 font-sans text-meta text-fg-subtle">
                {selectedEnvMeta}
              </Text>
            ) : null}
            <View className="mt-3">
              {selectedPlaceState === 'unreachable' ? (
                <Text className="font-sans text-caption text-fg-subtle">
                  발견되지 않은 영역입니다.
                </Text>
              ) : selectedDescription ? (
                <ExpandableDescription key={selectedNode.id} text={selectedDescription} />
              ) : null}
            </View>
          </View>
        </View>
      ) : null}
    </View>
  );
}
