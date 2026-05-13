import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { ExpandableTitle, ExpandGroup, LabeledRow, Row, characterMeta, joinOrDash } from '@/components/ui';
import { colors, toneColor } from '@/design/tokens';
import { compose, ko } from '@/locale/ko';
import type { PanelAction } from '@/logic/info-panel';

import type { StoryGraphEdge, StoryGraphModel } from '@/logic/story-graph/types';
import { StoryGraphCanvas } from './StoryGraphCanvas';
import { actionsForNode } from '@/logic/story-graph/_nodeActions';

const LEGEND: { key: string; label: string; color: string }[] = [
  { key: 'place', label: ko.legend.place, color: colors.exp.fg },
  { key: 'char', label: ko.legend.character, color: colors.success.fg },
  { key: 'quest', label: ko.legend.quest, color: colors.danger.fg },
];

export function NeighborhoodPanel({
  graph,
  framed = false,
  accessibilityLabel = ko.panel.storyGraph,
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
}: {
  graph: StoryGraphModel;
  framed?: boolean;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
}) {
  const visibleGraph: StoryGraphModel = React.useMemo(() => {
    // Neighborhood panel — restrict to the immediate neighborhood so the small
    // viewport doesn't get crammed with the full reachable map.
    const allowed = new Set<string>();
    for (const n of graph.nodes) {
      if (n.kind === 'place' || n.kind === 'hero' || n.kind === 'subject' || n.kind === 'quest') {
        allowed.add(n.id);
      } else if ((n.kind === 'location' || n.kind === 'target') && n.reachable) {
        allowed.add(n.id);
      }
    }
    const filteredNodes = graph.nodes.filter((n) => allowed.has(n.id));
    const pairToEdge = new Map<string, StoryGraphEdge>();
    for (const e of graph.edges) {
      if (!allowed.has(e.source) || !allowed.has(e.target)) continue;
      const pair = e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`;
      if (!pairToEdge.has(pair)) {
        pairToEdge.set(pair, e);
      }
    }
    return { ...graph, nodes: filteredNodes, edges: Array.from(pairToEdge.values()) };
  }, [graph]);

  const currentPlaceId = React.useMemo(
    () => visibleGraph.nodes.find((n) => n.kind === 'place')?.id ?? undefined,
    [visibleGraph.nodes],
  );

  const selectedNode = visibleGraph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedActions = selectedNode ? actionsForNode(selectedNode) : [];
  const isPlaceKind = !!selectedNode && (selectedNode.kind === 'place' || selectedNode.kind === 'location');
  const isCharacterKind = !!selectedNode && (selectedNode.kind === 'subject' || selectedNode.kind === 'target' || selectedNode.kind === 'hero');
  const isQuestKind = !!selectedNode && selectedNode.kind === 'quest';
  const selectedLabel = (() => {
    if (!selectedNode) return '';
    if (
      (selectedNode.kind === 'hero'
        || selectedNode.kind === 'subject'
        || selectedNode.kind === 'target')
      && selectedNode.alive === false
    ) {
      return compose.deceased(selectedNode.label);
    }
    return selectedNode.label;
  })();

  const placeFeatures = (() => {
    if (!isPlaceKind || !selectedNode) return null;
    if (!('risk' in selectedNode) || !selectedNode.risk) return null;
    return { risk: selectedNode.risk };
  })();
  const placeDescription = (() => {
    if (!isPlaceKind || !selectedNode) return null;
    if (!('description' in selectedNode)) return null;
    return selectedNode.description || '';
  })();
  const characterSections = (() => {
    if (!selectedNode) return null;
    if (selectedNode.kind !== 'subject' && selectedNode.kind !== 'target' && selectedNode.kind !== 'hero') return null;
    const known = selectedNode.kind === 'target'
      ? ''
      : selectedNode.known.length > 0 ? joinOrDash(selectedNode.known) : '';
    const trust = selectedNode.kind === 'hero' ? 0 : selectedNode.trust;
    return {
      desc: characterMeta(selectedNode.level, selectedNode.raceJob, selectedNode.gender),
      role: selectedNode.role || '',
      known,
      trust,
    };
  })();
  const questSections = (() => {
    if (!selectedNode || selectedNode.kind !== 'quest') return null;
    return {
      giver: selectedNode.giver || '',
      goals: selectedNode.goals.length > 0 ? joinOrDash(selectedNode.goals) : '',
      summary: selectedNode.summary || '',
    };
  })();
  const metaText = (() => {
    if (!selectedNode) return '';
    // Dead names already carry their own status, so suppress reachability metadata.
    if (
      (selectedNode.kind === 'hero'
        || selectedNode.kind === 'subject'
        || selectedNode.kind === 'target')
      && !selectedNode.alive
    ) {
      return '';
    }
    if (selectedNode.kind === 'place') return ko.panel.here;
    if (selectedNode.kind === 'subject') return ko.status.facing;
    if (selectedNode.kind === 'location' && selectedActions.length === 0) return ko.status.moveBlocked;
    if (selectedNode.kind === 'target' && !selectedNode.reachable) return ko.status.approachBlocked;
    if (selectedNode.kind === 'quest') return selectedNode.questDifficulty;
    return '';
  })();

  return (
    <View
      accessibilityLabel={`${accessibilityLabel}. ${visibleGraph.summary}`}
      className={`${framed ? 'border border-border-default rounded-sm bg-canvas-inset px-3 py-3' : 'px-4 pt-2 pb-3'} gap-2`}
    >
      <View style={{ aspectRatio: 1.618 }}>
        <StoryGraphCanvas
          graph={visibleGraph}
          accessibilityLabel={accessibilityLabel}
          selectedNodeId={selectedNodeId}
          onNodeSelect={onNodeSelect}
          centerNodeId={currentPlaceId}
        />
      </View>

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

      {selectedNode ? (
        <View className="border-t border-border-default pt-2.5 gap-2">
          <View className="gap-2.5">
            <View
              className="flex-row items-center gap-3"
              style={{ minHeight: 22 }}
            >
              <ExpandableTitle text={selectedLabel} />
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
            {isPlaceKind && placeFeatures ? (
              <Row label={ko.panel.environment}>
                <Text
                  numberOfLines={1}
                  className="font-sans text-panel text-fg-default"
                >
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
            <ExpandGroup>
              {isPlaceKind ? (
                placeDescription ? (
                  <LabeledRow label={ko.panel.appearance}>
                    {placeDescription}
                  </LabeledRow>
                ) : null
              ) : isCharacterKind && characterSections ? (
                <>
                  <LabeledRow label={ko.panel.description}>
                    {characterSections.desc}
                  </LabeledRow>
                  {characterSections.role ? (
                    <LabeledRow label={ko.panel.role}>
                      {characterSections.role}
                    </LabeledRow>
                  ) : null}
                  {characterSections.known ? (
                    <LabeledRow label={ko.panel.traits}>
                      {characterSections.known}
                    </LabeledRow>
                  ) : null}
                  {characterSections.trust !== 0 ? (
                    <Row label={ko.panel.affinity}>
                      <Text
                        className="font-sans-semibold text-panel"
                        style={{ color: toneColor[characterSections.trust >= 0 ? 'good' : 'bad'] }}
                      >
                        {characterSections.trust > 0 ? `+${characterSections.trust}` : `${characterSections.trust}`}
                      </Text>
                    </Row>
                  ) : null}
                </>
              ) : isQuestKind && questSections ? (
                <>
                  {questSections.giver ? (
                    <Row label={ko.panel.commission}>
                      <Text className="font-sans text-panel text-fg-default">
                        {questSections.giver}
                      </Text>
                    </Row>
                  ) : null}
                  {questSections.goals ? (
                    <LabeledRow label={ko.panel.goal}>
                      {questSections.goals}
                    </LabeledRow>
                  ) : null}
                  {questSections.summary ? (
                    <LabeledRow label={ko.panel.summary}>
                      {questSections.summary}
                    </LabeledRow>
                  ) : null}
                </>
              ) : null}
            </ExpandGroup>
          </View>
        </View>
      ) : null}
    </View>
  );
}
