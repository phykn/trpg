import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import React from 'react';

import { colors } from '@/design/tokens';
import type { StoryGraphModel, StoryGraphNodeKind } from '@/presenters/storyGraph';

const NODE_COLOR: Record<StoryGraphNodeKind, string> = {
  hero: colors.accent.fg,
  place: colors.exp.fg,
  subject: colors.success.fg,
  quest: colors.danger.fg,
  location: colors.exp.fg,
  target: colors.success.fg,
};

const NODE_SIZE: Record<StoryGraphNodeKind, number> = {
  hero: 42,
  place: 38,
  subject: 34,
  quest: 36,
  location: 28,
  target: 30,
};

type NodeOverride = {
  color?: string;
  size?: number;
  tier?: number;
  textColor?: string;
};

function seedPosition(index: number, total: number): { x: number; y: number } {
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const radius = 30 * Math.sqrt(index + 1);
  const angle = index * goldenAngle;
  return { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
}

function toElements(
  graph: StoryGraphModel,
  overrides?: Record<string, NodeOverride>,
  seedPositions = false,
): ElementDefinition[] {
  const total = graph.nodes.length;
  return [
    ...graph.nodes.map((node, idx) => {
      const override = overrides?.[node.id];
      return {
        data: {
          id: node.id,
          label: node.label,
          color: override?.color ?? NODE_COLOR[node.kind],
          size: override?.size ?? NODE_SIZE[node.kind],
          tier: override?.tier ?? 0,
          textColor: override?.textColor ?? colors.fg.default,
        },
        position: seedPositions ? seedPosition(idx, total) : undefined,
        classes: node.kind,
      };
    }),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
      },
    })),
  ];
}

export function StoryGraphCanvas({
  graph,
  height = 260,
  accessibilityLabel = '현재 스토리 그래프',
  selectedNodeId = null,
  onNodeSelect,
  nodeOverrides,
  arrows = true,
  edgeLabels = true,
  layout = 'cose',
  boxNodes = false,
  rootNodeId,
  centerNodeId,
  clearOnBackgroundTap = true,
}: {
  graph: StoryGraphModel;
  height?: number;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  nodeOverrides?: Record<string, NodeOverride>;
  arrows?: boolean;
  edgeLabels?: boolean;
  layout?: 'cose' | 'concentric' | 'breadthfirst';
  boxNodes?: boolean;
  rootNodeId?: string;
  centerNodeId?: string;
  clearOnBackgroundTap?: boolean;
}) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const cyRef = React.useRef<Core | null>(null);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const cy = cytoscape({
      container,
      elements: toElements(graph, nodeOverrides, boxNodes && layout === 'cose'),
      autoungrabify: boxNodes,
      hideEdgesOnViewport: true,
      minZoom: 0.55,
      maxZoom: 1.8,
      textureOnViewport: true,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: 'node',
          style: boxNodes
            ? {
                shape: 'round-rectangle',
                'background-color': 'data(color)',
                'border-color': colors.border.default,
                'border-width': 1,
                color: 'data(textColor)',
                content: 'data(label)',
                'font-family': 'NotoSerifKR_500Medium, serif',
                'font-size': 15,
                'text-valign': 'center',
                'text-halign': 'center',
                'text-wrap': 'none',
                width: 'label',
                height: 34,
                'padding-left': '12px',
                'padding-right': '12px',
                'overlay-opacity': 0,
              }
            : {
                'background-color': 'data(color)',
                'border-color': colors.canvas.subtle,
                'border-width': 2,
                color: colors.fg.default,
                content: 'data(label)',
                'font-family': 'NotoSerifKR_500Medium, serif',
                'font-size': 13,
                height: 'data(size)',
                label: 'data(label)',
                'min-zoomed-font-size': 10,
                'overlay-opacity': 0,
                'text-background-color': colors.canvas.subtle,
                'text-background-opacity': 0.92,
                'text-background-padding': '3px',
                'text-margin-y': 4,
                'text-valign': 'bottom',
                width: 'data(size)',
              },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': colors.accent.fg,
            'border-width': 4,
            'overlay-color': colors.accent.fg,
            'overlay-opacity': 0.12,
            'overlay-padding': 6,
          },
        },
        {
          selector: 'edge',
          style: {
            color: colors.fg.muted,
            'curve-style': 'bezier',
            'font-family': 'NotoSerifKR_400Regular, serif',
            'font-size': 8,
            label: edgeLabels ? 'data(label)' : '',
            'line-color': boxNodes ? colors.fg.subtle : colors.border.default,
            'overlay-opacity': 0,
            'target-arrow-color': boxNodes ? colors.fg.subtle : colors.border.default,
            'target-arrow-shape': arrows ? 'triangle' : 'none',
            'text-background-color': colors.canvas.subtle,
            'text-background-opacity': 0.72,
            'text-background-padding': '1px',
            'text-rotation': 'autorotate',
            width: boxNodes ? 1.8 : 1.4,
          },
        },
      ],
      layout:
        layout === 'breadthfirst'
          ? {
              name: 'breadthfirst',
              fit: true,
              padding: 16,
              spacingFactor: 1.0,
              directed: false,
              animate: false,
              roots: rootNodeId ? [rootNodeId] : undefined,
              circle: false,
              grid: false,
              avoidOverlap: true,
              maximal: false,
            }
          : layout === 'concentric'
            ? {
                name: 'concentric',
                fit: true,
                padding: 16,
                startAngle: (3 / 2) * Math.PI,
                minNodeSpacing: 18,
                spacingFactor: 1.05,
                avoidOverlap: true,
                concentric: (node: cytoscape.NodeSingular) => Number(node.data('tier') ?? 0),
                levelWidth: () => 1,
              }
            : {
                name: 'cose',
                animate: false,
                componentSpacing: 58,
                fit: true,
                idealEdgeLength: boxNodes ? 96 : 60,
                nodeOverlap: boxNodes ? 15 : 8,
                nodeRepulsion: boxNodes ? 6000 : 3500,
                padding: 14,
                randomize: false,
              },
    });

    cy.on('tap', 'node', (event) => {
      onNodeSelect?.(event.target.id());
    });
    if (clearOnBackgroundTap) {
      cy.on('tap', (event) => {
        if (event.target === cy) onNodeSelect?.(null);
      });
    }
    // layout runs synchronously when animate:false, so positions are ready here
    cy.fit(undefined, 16);
    if (centerNodeId) {
      const node = cy.getElementById(centerNodeId);
      if (node.length > 0) {
        const pos = node.position();
        const z = cy.zoom();
        cy.pan({
          x: cy.width() / 2 - pos.x * z,
          y: cy.height() / 2 - pos.y * z,
        });
      }
    }
    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, nodeOverrides, arrows, edgeLabels, layout, boxNodes, rootNodeId, centerNodeId, onNodeSelect, clearOnBackgroundTap]);

  React.useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (!selectedNodeId) return;
    const selected = cy.getElementById(selectedNodeId);
    if (selected.length > 0) selected.select();
  }, [graph, selectedNodeId]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={`${accessibilityLabel}. ${graph.summary}`}
      style={{
        backgroundColor: colors.canvas.default,
        borderColor: colors.border.default,
        borderRadius: 8,
        borderStyle: 'solid',
        borderWidth: 1,
        cursor: onNodeSelect ? 'pointer' : 'default',
        height,
        overflow: 'hidden',
        width: '100%',
      }}
    />
  );
}
