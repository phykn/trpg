import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import React from 'react';

import { colors } from '@/design/tokens';
import type { StoryGraphModel, StoryGraphNodeKind } from '@/presenters/storyGraph';

const NODE_COLOR: Record<StoryGraphNodeKind, string> = {
  hero: colors.accent.fg,
  place: colors.exp.fg,
  subject: '#567A8F',
  quest: colors.danger.fg,
  location: colors.border.default,
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

function toElements(graph: StoryGraphModel): ElementDefinition[] {
  return [
    ...graph.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.label,
        detail: node.detail,
        color: NODE_COLOR[node.kind],
        size: NODE_SIZE[node.kind],
      },
      classes: node.kind,
    })),
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
}: {
  graph: StoryGraphModel;
  height?: number;
  accessibilityLabel?: string;
  selectedNodeId?: string | null;
  onNodeSelect?: (nodeId: string | null) => void;
}) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const cyRef = React.useRef<Core | null>(null);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const cy = cytoscape({
      container,
      elements: toElements(graph),
      autoungrabify: false,
      hideEdgesOnViewport: true,
      minZoom: 0.55,
      maxZoom: 1.8,
      textureOnViewport: true,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'border-color': colors.canvas.subtle,
            'border-width': 2,
            color: colors.fg.default,
            content: 'data(label)',
            'font-family': 'NotoSerifKR_500Medium, serif',
            'font-size': 10,
            height: 'data(size)',
            label: 'data(label)',
            'min-zoomed-font-size': 8,
            'overlay-opacity': 0,
            'text-background-color': colors.canvas.subtle,
            'text-background-opacity': 0.86,
            'text-background-padding': '2px',
            'text-margin-y': 6,
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
            label: 'data(label)',
            'line-color': colors.border.default,
            'overlay-opacity': 0,
            'target-arrow-color': colors.border.default,
            'target-arrow-shape': 'triangle',
            'text-background-color': colors.canvas.subtle,
            'text-background-opacity': 0.72,
            'text-background-padding': '1px',
            'text-rotation': 'autorotate',
            width: 1.4,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        componentSpacing: 64,
        fit: true,
        idealEdgeLength: 86,
        nodeOverlap: 14,
        nodeRepulsion: 5600,
        padding: 28,
        randomize: false,
      },
    });

    cy.on('tap', 'node', (event) => {
      onNodeSelect?.(event.target.id());
    });
    cy.on('tap', (event) => {
      if (event.target === cy) onNodeSelect?.(null);
    });
    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, onNodeSelect]);

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
