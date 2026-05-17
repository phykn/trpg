import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import React from 'react';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { StoryGraphEdge, StoryGraphModel, StoryGraphNodeKind } from '@/logic/story-graph/types';

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
  item: colors.accent.fg,
};

const NODE_SIZE: Record<StoryGraphNodeKind, number> = {
  hero: 36,
  place: 32,
  subject: 30,
  quest: 30,
  location: 22,
  target: 24,
  item: 22,
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

function hashSeedPosition(id: string): { x: number; y: number } {
  // Deterministic spread across ~800×500 starting region. Without this every
  // first-time node shares position (0,0); cose then ties them apart with
  // internal randomness, producing different layouts each session. With it,
  // identical graphs yield identical layouts.
  let h = 0;
  for (let i = 0; i < id.length; i += 1) {
    h = (h * 1315423911 + id.charCodeAt(i)) | 0;
  }
  const ux = (h & 0xfffff) / 0xfffff;
  const uy = ((h >>> 12) & 0xfffff) / 0xfffff;
  return { x: ux * 800, y: uy * 500 };
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
      const seed =
        cachedPos
        ?? seedFromConnected(node.id, graph.edges, cached)
        ?? hashSeedPosition(node.id);
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
  height,
  accessibilityLabel = ko.panel.storyGraph,
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
  /** Explicit pixel height. Omit to let the component fill its parent (pair with an aspectRatio wrapper). */
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
  const hasMountedRef = React.useRef(false);
  const prevViewportRef = React.useRef<{ pan: { x: number; y: number }; zoom: number } | null>(null);
  const lifecycleGraphRef = React.useRef(graph);
  const centerNodeIdRef = React.useRef(centerNodeId);
  const unseenNodeIdsRef = React.useRef(unseenNodeIds);
  const onNodeSelectRef = React.useRef(onNodeSelect);
  const clearOnBackgroundTapRef = React.useRef(clearOnBackgroundTap);

  lifecycleGraphRef.current = graph;
  centerNodeIdRef.current = centerNodeId;
  unseenNodeIdsRef.current = unseenNodeIds;
  onNodeSelectRef.current = onNodeSelect;
  clearOnBackgroundTapRef.current = clearOnBackgroundTap;

  const graphIdentityKey = React.useMemo(() => {
    const ns = graph.nodes.map((n) => n.id).sort().join('|');
    const es = graph.edges.map((e) => `${e.source}>${e.target}`).sort().join('|');
    return `${ns}#${es}`;
  }, [graph]);

  // Effect 1: cy lifecycle — graph identity + the props that genuinely require
  // rebuilding (overrides/layout/root). Selection, callbacks, centerNodeId, and unseenNodeIds
  // are intentionally absent; they get their own effects so a tap doesn't reset zoom.
  React.useEffect(() => {
    const lifecycleGraph = lifecycleGraphRef.current;
    const lifecycleCenterNodeId = centerNodeIdRef.current;
    const lifecycleUnseenNodeIds = unseenNodeIdsRef.current;

    // Read viewport snapshot stashed by the previous cleanup, then clear it
    // so a stale value can't feed a future run.
    const prev = prevViewportRef.current;
    prevViewportRef.current = null;

    const validIds = new Set(lifecycleGraph.nodes.map((n) => n.id));
    for (const id of Object.keys(positionStore)) {
      if (!validIds.has(id)) delete positionStore[id];
    }

    const container = containerRef.current;
    if (!container) return undefined;

    const cy = cytoscape({
      container,
      elements: toElements(
        lifecycleGraph,
        nodeOverrides,
        lifecycleUnseenNodeIds,
        positionStore,
        lifecycleCenterNodeId,
      ),
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
            'font-size': 13,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 7,
            'text-wrap': 'none',
            'text-background-color': colors.canvas.default,
            'text-background-opacity': 0.85,
            'text-background-padding': 3,
            'text-background-shape': 'roundrectangle',
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
            'font-size': 13,
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 7,
            'text-wrap': 'none',
            'text-background-color': colors.canvas.default,
            'text-background-opacity': 0.85,
            'text-background-padding': 3,
            'text-background-shape': 'roundrectangle',
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
              fit: !hasMountedRef.current,
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
                fit: !hasMountedRef.current,
                padding: 16,
                startAngle: (3 / 2) * Math.PI,
                minNodeSpacing: 18,
                spacingFactor: 1.05,
                avoidOverlap: true,
                concentric: (node: cytoscape.NodeSingular) => Number(node.data('tier') ?? 0),
                levelWidth: () => 1,
              }
            : (() => {
              const allCached = lifecycleGraph.nodes.every((n) => positionStore[n.id]);
              const hasNewNodes = lifecycleUnseenNodeIds && lifecycleUnseenNodeIds.size > 0;
              return (allCached && !hasNewNodes)
                ? { name: 'preset', fit: !hasMountedRef.current, padding: 24 }
                : {
                    name: 'cose',
                    animate: false,
                    componentSpacing: 120,
                    fit: !hasMountedRef.current,
                    idealEdgeLength: 190,
                    nodeOverlap: 36,
                    nodeRepulsion: 22000,
                    gravity: 0.5,
                    numIter: 3500,
                    initialTemp: 240,
                    coolingFactor: 0.96,
                    padding: 24,
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
      onNodeSelectRef.current?.(event.target.id());
    });
    cy.on('tap', (event) => {
      if (event.target === cy && clearOnBackgroundTapRef.current) {
        onNodeSelectRef.current?.(null);
      }
    });
    // layout runs synchronously when animate:false, so positions are ready here
    if (!hasMountedRef.current) {
      // True first mount — fit + initial center.
      cy.fit(undefined, 28);
      if (lifecycleCenterNodeId) {
        const node = cy.getElementById(lifecycleCenterNodeId);
        if (node.length > 0) cy.center(node);
      }
      hasMountedRef.current = true;
    } else if (prev) {
      // Re-mount on topology / overrides change — preserve viewport.
      cy.zoom(prev.zoom);
      cy.pan(prev.pan);
    }
    cyRef.current = cy;

    return () => {
      prevViewportRef.current = { pan: cy.pan(), zoom: cy.zoom() };
      cy.destroy();
      cyRef.current = null;
    };
  }, [graphIdentityKey, nodeOverrides, layout, rootNodeId]);

  // Effect 2: selection — viewport untouched.
  React.useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (!selectedNodeId) return;
    const selected = cy.getElementById(selectedNodeId);
    if (selected.length > 0) selected.select();
  }, [selectedNodeId]);

  // Effect 3: camera follow — animated pan only, zoom preserved.
  React.useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !centerNodeId) return;
    const node = cy.getElementById(centerNodeId);
    if (node.length === 0) return;
    cy.ready(() => {
      const z = cy.zoom();
      const w = cy.width();
      const h = cy.height();
      const p = node.position();
      cy.animate(
        { pan: { x: -p.x * z + w / 2, y: -p.y * z + h / 2 } },
        { duration: 250 },
      );
    });
  }, [centerNodeId]);

  // Effect 4: unseen-state reflection — update node data without rebuilding cy.
  React.useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.nodes().forEach((node) => {
        const isNew = unseenNodeIds?.has(node.id()) ? 'true' : undefined;
        if (isNew) {
          node.data('isNew', isNew);
        } else {
          node.removeData('isNew');
        }
      });
    });
  }, [unseenNodeIds]);

  return (
    <div style={{ position: 'relative', width: '100%', height: height ?? '100%' }}>
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
          height: '100%',
          overflow: 'hidden',
          width: '100%',
        }}
      />
      <button
        type="button"
        aria-label={ko.panel.mapReset}
        onClick={() => cyRef.current?.fit(undefined, 28)}
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          padding: 6,
          background: colors.canvas.default,
          border: `1px solid ${colors.border.default}`,
          borderRadius: 6,
          color: colors.fg.default,
          cursor: 'pointer',
          opacity: 0.85,
        }}
      >
        <svg
          aria-hidden="true"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
        >
          <path
            d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6"
            stroke={colors.fg.default}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
