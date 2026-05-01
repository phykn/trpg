import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors, toneColor } from '@/design/tokens';
import {
  KIND_LABEL,
  type StoryGraphEdge,
  type StoryGraphModel,
  type StoryGraphNode,
} from '@/presenters/storyGraph';
import { SEP, characterMeta, joinOrDash } from '@/presenters/format';
import type { Place } from '@/types/domain';
import type { PanelAction } from '@/types/ui';

import { LabeledRow, Row } from '../ui';
import { StoryGraphCanvas } from './StoryGraphCanvas';

const COLOR_PLACE_UNREACH = '#DBC5A2';
const COLOR_CHAR_UNREACH = '#B5BEA8';

const LEGEND: { key: string; label: string; color: string }[] = [
  { key: 'place-reach', label: '이동 가능', color: colors.exp.fg },
  { key: 'place-unreach', label: '이동 불가', color: COLOR_PLACE_UNREACH },
  { key: 'char-reach', label: '만남 가능', color: colors.success.fg },
  { key: 'char-unreach', label: '만남 불가', color: COLOR_CHAR_UNREACH },
  { key: 'quest', label: '퀘스트', color: colors.danger.fg },
];

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

function moveIntent(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return `${name}로 이동합니다`;
  const final = (last - 0xac00) % 28;
  if (final === 0 || final === 8) return `${name}로 이동합니다`;
  return `${name}으로 이동합니다`;
}

function meetIntent(name: string): string {
  const last = name.charCodeAt(name.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return `${name}를 만납니다`;
  const final = (last - 0xac00) % 28;
  return final === 0 ? `${name}를 만납니다` : `${name}을 만납니다`;
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
  if (node.kind === 'target') {
    return { label: '만남', intent: meetIntent(node.label) };
  }
  return null;
}

export function StoryGraphPanel({
  graph,
  canvasHeight = 260,
  framed = false,
  accessibilityLabel = '현재 스토리 그래프',
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
  mapView = false,
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
  mapView?: boolean;
  place?: Place | null;
}) {
  const placeStates = React.useMemo<Record<string, PlaceState> | null>(() => {
    if (!mapView) return null;
    return Object.fromEntries(
      graph.nodes
        .filter((n) => n.kind === 'place' || n.kind === 'location')
        .map((n) => {
          if (n.kind === 'place') return [n.id, 'current' as PlaceState];
          return [n.id, isReachableFromCurrentPlace(n, graph) ? 'reachable' : 'unreachable'];
        }),
    );
  }, [graph, mapView]);

  const visibleGraph: StoryGraphModel = React.useMemo(() => {
    if (!mapView) {
      const currentPlaceId = graph.nodes.find((n) => n.kind === 'place')?.id;
      const currentSubjectId = graph.nodes.find((n) => n.kind === 'subject')?.id;
      return {
        ...graph,
        edges: graph.edges.map((edge) => {
          if (edge.label === '현재 위치' && edge.target === currentPlaceId) {
            return { ...edge, label: '위치' };
          }
          if (edge.label === '주시' && edge.target === currentSubjectId) {
            return { ...edge, label: '대상' };
          }
          return { ...edge, label: '' };
        }),
      };
    }
    const placeNodes = graph.nodes.filter((n) => n.kind === 'place' || n.kind === 'location');
    const placeIds = new Set(placeNodes.map((n) => n.id));
    const seenPair = new Set<string>();
    const placeEdges: StoryGraphEdge[] = [];
    for (const e of graph.edges) {
      if (e.label !== '이동') continue;
      if (!placeIds.has(e.source) || !placeIds.has(e.target)) continue;
      const pair = e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`;
      if (seenPair.has(pair)) continue;
      seenPair.add(pair);
      placeEdges.push(e);
    }
    const currentPlace = placeNodes.find((n) => n.kind === 'place');
    const reachableCount = placeNodes.filter(
      (n) => n.kind === 'location' && placeStates?.[n.id] === 'reachable',
    ).length;
    const summary = [
      currentPlace ? `현재 ${currentPlace.label}` : null,
      `장소 ${placeNodes.length}곳`,
      `이동 가능 ${reachableCount}`,
    ]
      .filter(Boolean)
      .join(SEP);
    return { nodes: placeNodes, edges: placeEdges, summary };
  }, [graph, mapView, placeStates]);

  const nodeOverrides = React.useMemo(() => {
    if (placeStates) {
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
    }
    const out: Record<string, { color: string; tier: number; textColor: string }> = {};
    for (const node of graph.nodes) {
      if (node.kind !== 'location' && node.kind !== 'target') continue;
      if (!isReachableFromCurrentPlace(node, graph)) {
        out[node.id] = {
          color: node.kind === 'location' ? COLOR_PLACE_UNREACH : COLOR_CHAR_UNREACH,
          tier: 1,
          textColor: colors.fg.muted,
        };
      }
    }
    return Object.keys(out).length > 0 ? out : undefined;
  }, [graph, placeStates]);

  const selectedNode = visibleGraph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedAction = selectedNode ? actionForNode(selectedNode, graph) : null;
  const isPlaceKind = !!selectedNode && (selectedNode.kind === 'place' || selectedNode.kind === 'location');
  const placeFeatures = (() => {
    if (mapView || !isPlaceKind || !selectedNode) return null;
    if (!selectedNode.risk) return null;
    const weather = (place?.weather ?? []).filter(Boolean).join(SEP);
    return { weather, risk: selectedNode.risk };
  })();
  const placeDescription = (() => {
    if (mapView || !isPlaceKind || !selectedNode) return null;
    return selectedNode.description || '';
  })();
  const charReachable: boolean | null = (() => {
    if (mapView || !selectedNode) return null;
    if (selectedNode.kind !== 'subject' && selectedNode.kind !== 'target') return null;
    return isReachableFromCurrentPlace(selectedNode, graph);
  })();
  const characterSections = (() => {
    if (mapView || !selectedNode) return null;
    if (selectedNode.kind !== 'subject' && selectedNode.kind !== 'target') return null;
    if (selectedNode.level === undefined || selectedNode.raceJob === undefined) return null;
    return {
      desc: characterMeta(selectedNode.level, selectedNode.raceJob, selectedNode.gender ?? ''),
      role: selectedNode.role || '',
      known: selectedNode.known ? joinOrDash(selectedNode.known) : '',
      trust: selectedNode.trust ?? 0,
    };
  })();
  const selectedPlaceState: PlaceState | null =
    mapView && selectedNode && placeStates ? placeStates[selectedNode.id] ?? null : null;
  const selectedPlaceLabel = selectedPlaceState
    ? PLACE_LEGEND.find((p) => p.state === selectedPlaceState)?.label ?? null
    : null;
  const selectedDescription: string | null = (() => {
    if (!mapView || !selectedNode || !place) return null;
    if (selectedPlaceState === 'current') return place.description || null;
    if (selectedPlaceState === 'reachable') {
      const s = place.surroundings.find((s) => s.name === selectedNode.label);
      return s?.blurb || null;
    }
    return null;
  })();
  const selectedMeta: string | null = (() => {
    if (!mapView || !selectedNode || !place) return null;
    if (selectedPlaceState === 'current') {
      return [place.dayPhase, ...place.weather, place.risk.label].filter(Boolean).join(SEP);
    }
    if (selectedPlaceState === 'reachable') {
      const s = place.surroundings.find((s) => s.name === selectedNode.label);
      if (!s) return null;
      return [s.risk.label, s.difficulty ? `이동 난이도: ${s.difficulty}` : null]
        .filter(Boolean)
        .join(SEP);
    }
    return null;
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
        edgeLabels={!mapView}
        layout="cose"
        boxNodes={mapView}
        centerNodeId={mapView ? visibleGraph.nodes.find((n) => n.kind === 'place')?.id : undefined}
        clearOnBackgroundTap={false}
      />

      {!mapView && (
        <View className="flex-row flex-wrap items-center justify-center gap-x-3 gap-y-1">
          {LEGEND.map((item) => (
            <View key={item.key} className="flex-row items-center gap-1">
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
      )}

      {selectedNode ? (
        <View className="border-t border-border-default pt-2.5 gap-2">
          {mapView ? (
            <View>
              <Text className="font-sans text-meta text-fg-subtle">
                {selectedPlaceLabel ?? KIND_LABEL[selectedNode.kind]}
              </Text>
              <View className="mt-1 flex-row items-baseline justify-between gap-3">
                <Text numberOfLines={1} className="flex-1 min-w-0 font-serif-medium text-title text-fg-default">
                  {selectedNode.label}
                </Text>
                {selectedMeta ? (
                  <Text numberOfLines={1} className="font-sans text-meta text-fg-subtle">
                    {selectedMeta}
                  </Text>
                ) : null}
              </View>
              <View className="mt-3">
                {selectedPlaceState === 'unreachable' ? (
                  <Text className="font-sans text-caption text-fg-subtle">
                    발견되지 않은 영역입니다.
                  </Text>
                ) : selectedDescription ? (
                  <Text className="font-sans text-caption text-fg-muted" style={{ lineHeight: 20 }}>
                    {selectedDescription}
                  </Text>
                ) : null}
              </View>
              {selectedAction && onAction ? (
                <View className="mt-3 flex-row justify-end">
                  <Pressable
                    onPress={() => onAction(selectedAction)}
                    disabled={actionDisabled}
                    accessibilityRole="button"
                    accessibilityLabel={`${selectedNode.label} 이동`}
                    className={`rounded-sm border border-border-default px-4 py-1.5 ${actionDisabled ? 'bg-canvas-inset opacity-60' : 'bg-canvas-default active:bg-canvas-inset'}`}
                  >
                    <Text className="font-sans-semibold text-panel text-fg-default">
                      {actionDisabled ? '처리 중' : selectedAction.label}
                    </Text>
                  </Pressable>
                </View>
              ) : null}
            </View>
          ) : (
            (() => {
              const metaText = (() => {
                if (selectedNode.kind === 'place') return '현재 위치';
                if (selectedNode.kind === 'subject') return '대면 중';
                if (selectedNode.kind === 'location' && !selectedAction) return '이동 불가';
                if (selectedNode.kind === 'target' && !charReachable) return '만남 불가';
                return '';
              })();
              const isCharacterKind = selectedNode.kind === 'subject' || selectedNode.kind === 'target';
              return (
                <View className="gap-2.5">
                  <View
                    className="flex-row items-center gap-2"
                    style={{ minHeight: 22 }}
                  >
                    <View className="flex-1 min-w-0">
                      <Text
                        numberOfLines={1}
                        className="font-serif-medium text-title text-fg-default"
                      >
                        {selectedNode.label}
                      </Text>
                    </View>
                    {metaText ? (
                      <View className="flex-1 min-w-0">
                        <Text
                          numberOfLines={1}
                          className="font-sans text-caption italic text-right text-fg-muted"
                        >
                          {metaText}
                        </Text>
                      </View>
                    ) : null}
                  </View>
                  {isPlaceKind && placeFeatures ? (
                    <Row label="환경">
                      <Text
                        numberOfLines={1}
                        className="font-sans text-panel text-fg-default"
                      >
                        {placeFeatures.weather}
                        {placeFeatures.weather && placeFeatures.risk ? SEP : ''}
                        {placeFeatures.risk ? (
                          <Text
                            className="font-sans-semibold"
                            style={{ color: toneColor[placeFeatures.risk.tone] }}
                          >
                            {placeFeatures.risk.label}
                          </Text>
                        ) : null}
                      </Text>
                    </Row>
                  ) : null}
                  {isPlaceKind ? (
                    placeDescription ? (
                      <LabeledRow label="모습">
                        {placeDescription}
                      </LabeledRow>
                    ) : null
                  ) : isCharacterKind && characterSections ? (
                    <>
                      <LabeledRow label="설명">
                        {characterSections.desc}
                      </LabeledRow>
                      {characterSections.role ? (
                        <LabeledRow label="역할">
                          {characterSections.role}
                        </LabeledRow>
                      ) : null}
                      {characterSections.known ? (
                        <LabeledRow label="특징">
                          {characterSections.known}
                        </LabeledRow>
                      ) : null}
                      {characterSections.trust !== 0 ? (
                        <Row label="호감도">
                          <Text
                            className="font-sans-semibold text-panel"
                            style={{ color: toneColor[characterSections.trust >= 0 ? 'good' : 'bad'] }}
                          >
                            {characterSections.trust > 0 ? `+${characterSections.trust}` : `${characterSections.trust}`}
                          </Text>
                        </Row>
                      ) : null}
                    </>
                  ) : null}
                  {selectedAction && onAction ? (
                    <View className="flex-row justify-end">
                      <Pressable
                        onPress={() => onAction(selectedAction)}
                        disabled={actionDisabled}
                        accessibilityRole="button"
                        accessibilityLabel={`${selectedNode.label} ${selectedAction.label}`}
                        className={`rounded-sm border border-border-default px-4 py-1.5 ${actionDisabled ? 'bg-canvas-inset opacity-60' : 'bg-canvas-default active:bg-canvas-inset'}`}
                      >
                        <Text className="font-sans-semibold text-panel text-fg-default">
                          {actionDisabled ? '처리 중' : selectedAction.label}
                        </Text>
                      </Pressable>
                    </View>
                  ) : null}
                </View>
              );
            })()
          )}
        </View>
      ) : null}
    </View>
  );
}
