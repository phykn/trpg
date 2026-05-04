import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import React from 'react';

import { colors } from '@/design/tokens';
import type { StoryGraphEdge, StoryGraphModel, StoryGraphNodeKind } from './presenters';

// Module-scoped so positions survive panel switches (component remount).
// Keyed by nodeId; scenario-unique IDs make cross-game collision unlikely,
// and stale entries are pruned each effect run against the current graph.
const positionStore: Record<string, { x: number; y: number }> = {};

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

function hashJitter(id: string): { dx: number; dy: number } {
  // Deterministic small offset (~±35 px) so newly added nodes don't all stack at the centroid.
  let h = 0;
  for (let i = 0; i < id.length; i += 1) {
    h = (h * 31 + id.charCodeAt(i)) | 0;
  }
  const dx = ((h & 0xffff) / 0xffff - 0.5) * 70;  // ±35px
  const dy = (((h >> 16) & 0xffff) / 0xffff - 0.5) * 70;
  return { dx, dy };
}

function seedFromConnected(
  nodeId: string,
  edges: StoryGraphEdge[],
  cached: Record<string, { x: number; y: number }>,
): { x: number; y: number } | undefined {
  const connected: string[] = [];
  for (const e of edges) {
    if (e.source === nodeId && cached[e.target]) connected.push(e.target);
    else if (e.target === nodeId && cached[e.source]) connected.push(e.source);
  }
  if (connected.length === 0) return undefined;
  let sx = 0;
  let sy = 0;
  for (const cid of connected) {
    sx += cached[cid].x;
    sy += cached[cid].y;
  }
  const cx = sx / connected.length;
  const cy_ = sy / connected.length;
  const { dx, dy } = hashJitter(nodeId);
  return { x: cx + dx, y: cy_ + dy };
}

function toElements(
  graph: StoryGraphModel,
  overrides: Record<string, NodeOverride> | undefined,
  unseenNodeIds: Set<string> | undefined,
  cached: Record<string, { x: number; y: number }>,
  centerNodeId: string | undefined,
): ElementDefinition[] {
  return [
    ...graph.nodes.map((node) => {
      const override = overrides?.[node.id];
      const cachedPos = cached[node.id];
      const seed = cachedPos ?? seedFromConnected(node.id, graph.edges, cached);
      const isCurrent = centerNodeId !== undefined && node.id === centerNodeId;
      return {
        data: {
          id: node.id,
          label: node.label,
          color: override?.color ?? NODE_COLOR[node.kind],
          size: override?.size ?? NODE_SIZE[node.kind],
          tier: override?.tier ?? 0,
          textColor: override?.textColor ?? colors.fg.default,
          isNew: unseenNodeIds?.has(node.id) ? 'true' : undefined,
          interactable: node.reachable ? 'true' : 'false',
        },
        position: seed,
        locked: cachedPos !== undefined,
        classes: `${node.kind} ${isCurrent ? 'current' : ''}`.trim(),
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
  height = 320,
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
    // Drop cache entries for nodes no longer in the graph.
    const validIds = new Set(graph.nodes.map((n) => n.id));
    for (const id of Object.keys(positionStore)) {
      if (!validIds.has(id)) delete positionStore[id];
    }

    const container = containerRef.current;
    if (!container) return undefined;

    const cy = cytoscape({
      container,
      elements: toElements(graph, nodeOverrides, unseenNodeIds, positionStore, centerNodeId),
      autoungrabify: true,
      hideEdgesOnViewport: false,
      minZoom: 0.2,
      maxZoom: 1.8,
      textureOnViewport: false,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: 'node[interactable = "true"]',
          style: {
            'background-color': 'data(color)',
            'border-color': colors.border.default,
            'border-width': 1,
            color: 'data(textColor)',
            content: 'data(label)',
            'font-family': 'NanumGothic_700Bold, serif',
            'font-size': 14,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'text-wrap': 'none',
            'text-background-opacity': 0,
            'text-border-opacity': 0,
            'text-border-width': 0,
            width: 'data(size)',
            height: 'data(size)',
            'overlay-opacity': 0,
          },
        },
        {
          selector: 'node[interactable = "false"]',
          style: {
            'background-color': 'transparent',
            'border-color': 'data(color)',
            'border-width': 1.5,
            color: colors.fg.muted,
            content: 'data(label)',
            'font-family': 'NanumGothic_700Bold, serif',
            'font-size': 14,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'text-wrap': 'none',
            'text-background-opacity': 0,
            'text-border-opacity': 0,
            'text-border-width': 0,
            width: 'data(size)',
            height: 'data(size)',
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
          selector: 'node.current',
          style: {
            'border-color': colors.accent.fg,
            'border-width': 4,
            'overlay-color': colors.accent.fg,
            'overlay-opacity': 0.12,
            'overlay-padding': 4,
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'line-color': colors.border.default,
            'overlay-opacity': 0,
            'target-arrow-shape': 'none',
            width: 2.4,
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
            : (() => {
              const allCached = graph.nodes.every((n) => positionStore[n.id]);
              const hasNewNodes = unseenNodeIds && unseenNodeIds.size > 0;
              return (allCached && !hasNewNodes)
                ? { name: 'preset', fit: true, padding: 14 }
                : {
                    name: 'cose',
                    animate: false,
                    componentSpacing: 80,
                    fit: true,
                    idealEdgeLength: 110,
                    nodeOverlap: 20,
                    nodeRepulsion: 9000,
                    gravity: 0.4,
                    numIter: 2500,
                    initialTemp: 220,
                    coolingFactor: 0.95,
                    padding: 14,
                    randomize: false,
                  };
            })(),
    } as any);

    // Capture positions synchronously — `cytoscape({layout: ..., animate: false})`
    // runs layout inside the constructor, so the layoutstop event fires before any
    // listener could be attached. Save positions now while cy is fresh.
    cy.nodes().forEach((node) => {
      const pos = node.position();
      positionStore[node.id()] = { x: pos.x, y: pos.y };
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
    cy.fit(undefined, 12);
    if (centerNodeId) {
      const node = cy.getElementById(centerNodeId);
      if (node.length > 0) {
        cy.center(node);
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
