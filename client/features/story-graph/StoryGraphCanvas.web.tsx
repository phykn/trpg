import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import React from 'react';

import { colors } from '@/design/tokens';
import type { StoryGraphModel, StoryGraphNodeKind } from './presenters';

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

function toElements(
  graph: StoryGraphModel,
  overrides?: Record<string, NodeOverride>,
  unseenNodeIds?: Set<string>,
): ElementDefinition[] {
  return [
    ...graph.nodes.map((node) => {
      const override = overrides?.[node.id];
      return {
        data: {
          id: node.id,
          label: node.label,
          color: override?.color ?? NODE_COLOR[node.kind],
          size: override?.size ?? NODE_SIZE[node.kind],
          tier: override?.tier ?? 0,
          textColor: override?.textColor ?? colors.fg.default,
          isNew: unseenNodeIds?.has(node.id) ? 'true' : undefined,
        },
        classes: node.kind,
      };
    }),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
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
  layout = 'cose',
  rootNodeId,
  centerNodeId,
  clearOnBackgroundTap = true,
  unseenNodeIds,
}: {
  graph: StoryGraphModel;
  height?: number;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
  nodeOverrides?: Record<string, NodeOverride>;
  layout?: 'cose' | 'concentric' | 'breadthfirst';
  rootNodeId?: string;
  centerNodeId?: string;
  clearOnBackgroundTap?: boolean;
  unseenNodeIds?: Set<string>;
}) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const cyRef = React.useRef<Core | null>(null);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const cy = cytoscape({
      container,
      elements: toElements(graph, nodeOverrides, unseenNodeIds),
      autoungrabify: true,
      hideEdgesOnViewport: true,
      minZoom: 0.55,
      maxZoom: 1.8,
      textureOnViewport: true,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: 'node',
          style: {
            shape: 'round-rectangle',
            'background-color': 'data(color)',
            'border-color': colors.border.default,
            'border-width': 1,
            color: 'data(textColor)',
            content: 'data(label)',
            'font-family': 'NanumGothic_700Bold, serif',
            'font-size': 17,
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'none',
            width: 'label',
            height: 34,
            'padding-left': '12px',
            'padding-right': '12px',
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': colors.accent.fg,
            'border-width': 4,
          },
        },
        {
          selector: 'node[isNew = "true"]',
          style: {
            'overlay-color': colors.accent.fg,
            'overlay-opacity': 0.18,
            'overlay-padding': 5,
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'line-color': colors.fg.subtle,
            'overlay-opacity': 0,
            'target-arrow-shape': 'none',
            width: 1.8,
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
                idealEdgeLength: 96,
                nodeOverlap: 15,
                nodeRepulsion: 6000,
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
  }, [graph, nodeOverrides, layout, rootNodeId, centerNodeId, onNodeSelect, clearOnBackgroundTap, unseenNodeIds]);

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
