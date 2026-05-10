import type { StoryGraphEdge, StoryGraphModel, StoryGraphNode } from './types';

export type NativeStoryGraphLayoutNode = {
  id: string;
  label: string;
  kind: StoryGraphNode['kind'];
  x: number;
  y: number;
  current: boolean;
  reachable: boolean;
  selected: boolean;
};

export type NativeStoryGraphLayoutEdge = StoryGraphEdge & {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type NativeStoryGraphLayout = {
  nodes: NativeStoryGraphLayoutNode[];
  edges: NativeStoryGraphLayoutEdge[];
};

type NativeLayoutOptions = {
  width: number;
  height: number;
  centerNodeId?: string | null;
  selectedNodeId?: string | null;
};

const NODE_MARGIN_X = 36;
const NODE_MARGIN_TOP = 28;
const NODE_MARGIN_BOTTOM = 36;

export function layoutNativeStoryGraph(
  graph: StoryGraphModel,
  options: NativeLayoutOptions,
): NativeStoryGraphLayout {
  const width = Math.max(1, Math.round(options.width));
  const height = Math.max(1, Math.round(options.height));
  const centerNode = pickCenterNode(graph.nodes, options.centerNodeId);
  const orderedNodes = centerNode
    ? [centerNode, ...graph.nodes.filter((node) => node.id !== centerNode.id)]
    : graph.nodes;

  const centerX = Math.round(width / 2);
  const centerY = Math.round(height * 0.46);
  const otherCount = Math.max(0, orderedNodes.length - 1);
  const radiusX = Math.max(0, Math.min(width * 0.34, width / 2 - NODE_MARGIN_X));
  const radiusY = Math.max(0, Math.min(height * 0.3, height / 2 - NODE_MARGIN_BOTTOM));

  const nodes = orderedNodes.map((node, index) => {
    const point =
      index === 0 && centerNode
        ? { x: centerX, y: centerY }
        : pointAroundCenter(index - (centerNode ? 1 : 0), otherCount || orderedNodes.length, {
            centerX,
            centerY,
            radiusX,
            radiusY,
            width,
            height,
          });

    return {
      id: node.id,
      label: node.label,
      kind: node.kind,
      x: point.x,
      y: point.y,
      current: node.kind === 'place' || node.id === centerNode?.id,
      reachable: node.reachable,
      selected: options.selectedNodeId === node.id,
    };
  });

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = graph.edges.flatMap((edge) => {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) return [];
    return [{
      ...edge,
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
    }];
  });

  return { nodes, edges };
}

function pickCenterNode(
  nodes: StoryGraphNode[],
  centerNodeId: string | null | undefined,
): StoryGraphNode | null {
  return (
    nodes.find((node) => node.id === centerNodeId)
    ?? nodes.find((node) => node.kind === 'place')
    ?? nodes[0]
    ?? null
  );
}

function pointAroundCenter(
  index: number,
  count: number,
  bounds: {
    centerX: number;
    centerY: number;
    radiusX: number;
    radiusY: number;
    width: number;
    height: number;
  },
) {
  const angle = count === 1
    ? 0
    : (count === 2 ? 0 : -Math.PI / 2) + (index * 2 * Math.PI) / count;
  const x = Math.round(bounds.centerX + Math.cos(angle) * bounds.radiusX);
  const y = Math.round(bounds.centerY + Math.sin(angle) * bounds.radiusY);
  return {
    x: clamp(x, NODE_MARGIN_X, bounds.width - NODE_MARGIN_X),
    y: clamp(y, NODE_MARGIN_TOP, bounds.height - NODE_MARGIN_BOTTOM),
  };
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return Math.round((min + max) / 2);
  return Math.min(max, Math.max(min, value));
}
