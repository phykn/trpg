import { ko } from '@/locale/ko';
import type {
  StoryGraphEdge,
  StoryGraphModel,
  StoryGraphNode,
  StoryGraphNodeKind,
} from './types';

const NODE_KIND = new Set<StoryGraphNodeKind>([
  'hero',
  'place',
  'subject',
  'quest',
  'location',
  'target',
]);

export const EMPTY_STORY_GRAPH: StoryGraphModel = {
  nodes: [],
  edges: [],
  summary: ko.panel.noStoryData,
};

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

// Merge stored + current graphs. Demote `place` → `location` and `subject` → `target` when no longer active.
export function mergeStoryGraphs(base: StoryGraphModel, next: StoryGraphModel): StoryGraphModel {
  if (base.nodes.length === 0 && base.edges.length === 0) return next;
  if (next.nodes.length === 0 && next.edges.length === 0) return base;

  const nextPlaceIds = new Set(next.nodes.filter((n) => n.kind === 'place').map((n) => n.id));
  const nextSubjectIds = new Set(next.nodes.filter((n) => n.kind === 'subject').map((n) => n.id));
  const nextIds = new Set(next.nodes.map((n) => n.id));

  const nodes = new Map<string, StoryGraphNode>();
  for (const node of base.nodes) {
    if (nextIds.has(node.id)) continue;
    let demoted: StoryGraphNode = node;
    if (node.kind === 'place' && !nextPlaceIds.has(node.id)) {
      demoted = {
        id: node.id,
        label: node.label,
        kind: 'location',
        status: 'unreachable_move',
        reachable: false,
        description: node.description,
        risk: node.risk,
        moveDifficulty: null,
      };
    } else if (node.kind === 'subject' && !nextSubjectIds.has(node.id)) {
      demoted = {
        id: node.id,
        label: node.label,
        kind: 'target',
        status: 'unreachable_meet',
        reachable: false,
        alive: node.alive,
        level: node.level,
        raceJob: node.raceJob,
        gender: node.gender,
        role: node.role,
        trust: node.trust,
      };
    }
    nodes.set(demoted.id, demoted);
  }
  for (const node of next.nodes) {
    nodes.set(node.id, node);
  }

  const validIds = new Set(nodes.keys());
  const edges = new Map<string, StoryGraphEdge>();
  for (const edge of base.edges) {
    if (!validIds.has(edge.source) || !validIds.has(edge.target)) continue;
    edges.set(edge.id, edge);
  }
  for (const edge of next.edges) {
    edges.set(edge.id, edge);
  }

  return {
    nodes: Array.from(nodes.values()),
    edges: Array.from(edges.values()),
    summary: next.summary,
  };
}

export function storyGraphFingerprint(graph: StoryGraphModel): string {
  const nodes = graph.nodes
    .map((node) => JSON.stringify(node))
    .sort()
    .join('|');
  const edges = graph.edges
    .map((edge) => `${edge.id}:${edge.source}:${edge.target}:${edge.label}`)
    .sort()
    .join('|');
  return `${graph.summary}::${nodes}::${edges}`;
}

function isValidStoredNode(raw: unknown): raw is StoryGraphNode {
  if (!isObject(raw)) return false;
  if (typeof raw.id !== 'string' || typeof raw.label !== 'string') return false;
  if (!NODE_KIND.has(raw.kind as StoryGraphNodeKind)) return false;
  if (raw.kind === 'subject' || raw.kind === 'target') {
    return typeof raw.level === 'number' && typeof raw.raceJob === 'string';
  }
  if (raw.kind === 'place' || raw.kind === 'location') {
    return typeof raw.description === 'string';
  }
  if (raw.kind === 'hero') {
    return typeof raw.level === 'number' && typeof raw.raceJob === 'string';
  }
  if (raw.kind === 'quest') {
    return typeof raw.questDifficulty === 'string';
  }
  return true;
}

export function isValidStoryGraph(raw: unknown): raw is StoryGraphModel {
  if (!isObject(raw)) return false;
  if (!Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) return false;
  return raw.nodes.every(isValidStoredNode);
}
