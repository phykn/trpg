import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors, toneColor } from '@/design/tokens';
import {
  type StoryGraphEdge,
  type StoryGraphModel,
} from '@/presenters/storyGraph';
import { SEP, characterMeta, joinOrDash } from '@/presenters/format';
import type { PanelAction } from '@/types/ui';

import { ExpandableTitle, ExpandGroup, LabeledRow, Row } from '../ui';
import { StoryGraphCanvas } from './StoryGraphCanvas';
import { actionForNode } from './_nodeActions';

const COLOR_PLACE_UNREACH = '#DBC5A2';
const COLOR_CHAR_UNREACH = '#B5BEA8';

const LEGEND: { key: string; label: string; color: string }[] = [
  { key: 'place-reach', label: '이동 가능', color: colors.exp.fg },
  { key: 'place-unreach', label: '이동 불가', color: COLOR_PLACE_UNREACH },
  { key: 'char-reach', label: '접근 가능', color: colors.success.fg },
  { key: 'char-unreach', label: '접근 불가', color: COLOR_CHAR_UNREACH },
  { key: 'quest', label: '퀘스트', color: colors.danger.fg },
];

export function NeighborhoodPanel({
  graph,
  canvasHeight = 260,
  framed = false,
  accessibilityLabel = '현재 스토리 그래프',
  selectedNodeId = null,
  onNodeSelect,
  onAction,
  actionDisabled = false,
}: {
  graph: StoryGraphModel;
  canvasHeight?: number;
  framed?: boolean;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onAction?: (action: PanelAction) => void;
  actionDisabled?: boolean;
}) {
  const visibleGraph: StoryGraphModel = React.useMemo(() => {
    const transformed = graph.edges.map((edge) => {
      if (edge.kind === 'current_pin') return { ...edge, label: '위치' };
      if (edge.kind === 'observe') return { ...edge, label: '대상' };
      return { ...edge, label: '' };
    });
    // Collapse parallel edges between the same two nodes — keep a labeled
    // edge over an unlabeled one when both exist.
    const pairToEdge = new Map<string, StoryGraphEdge>();
    for (const e of transformed) {
      const pair = e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`;
      const existing = pairToEdge.get(pair);
      if (!existing || (e.label && !existing.label)) {
        pairToEdge.set(pair, e);
      }
    }
    return { ...graph, edges: Array.from(pairToEdge.values()) };
  }, [graph]);

  const nodeOverrides = React.useMemo(() => {
    const out: Record<string, { color: string; tier: number; textColor: string }> = {};
    for (const node of graph.nodes) {
      if (node.kind !== 'location' && node.kind !== 'target') continue;
      if (node.reachable === false) {
        out[node.id] = {
          color: node.kind === 'location' ? COLOR_PLACE_UNREACH : COLOR_CHAR_UNREACH,
          tier: 1,
          textColor: colors.fg.muted,
        };
      }
    }
    return Object.keys(out).length > 0 ? out : undefined;
  }, [graph]);

  const selectedNode = visibleGraph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedAction = selectedNode ? actionForNode(selectedNode) : null;
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
      return `${selectedNode.label} (죽음)`;
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
    // Dead names carry "(죽음)"; suppress reachability label to avoid "(죽음) · 만남 불가".
    if (
      (selectedNode.kind === 'hero'
        || selectedNode.kind === 'subject'
        || selectedNode.kind === 'target')
      && !selectedNode.alive
    ) {
      return '';
    }
    if (selectedNode.kind === 'place') return '현재 위치';
    if (selectedNode.kind === 'subject') return '대면 중';
    if (selectedNode.kind === 'location' && !selectedAction) return '이동 불가';
    if (selectedNode.kind === 'target' && !selectedNode.reachable) return '접근 불가';
    if (selectedNode.kind === 'quest') return selectedNode.questDifficulty;
    return '';
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
        edgeLabels
        layout="cose"
        clearOnBackgroundTap={false}
      />

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
            {isPlaceKind && placeFeatures ? (
              <Row label="환경">
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
              ) : isQuestKind && questSections ? (
                <>
                  {questSections.giver ? (
                    <Row label="의뢰">
                      <Text className="font-sans text-panel text-fg-default">
                        {questSections.giver}
                      </Text>
                    </Row>
                  ) : null}
                  {questSections.goals ? (
                    <LabeledRow label="목표">
                      {questSections.goals}
                    </LabeledRow>
                  ) : null}
                  {questSections.summary ? (
                    <LabeledRow label="요약">
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
