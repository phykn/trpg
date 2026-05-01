import type { Hero, Place, Quest, RiskBadge, Subject } from '@/types/domain';
import type { StoryGraphPayload } from '@/types/wire';

import { SEP } from './format';

export type StoryGraphNodeKind = 'hero' | 'place' | 'subject' | 'quest' | 'location' | 'target';

const NODE_KIND = new Set<StoryGraphNodeKind>([
  'hero',
  'place',
  'subject',
  'quest',
  'location',
  'target',
]);

// Flat shape with optional kind-specific fields. Producers populate the
// fields for the kind they emit; consumers branch on kind and read the
// matching fields directly — never re-parse a combined display string.
export type StoryGraphNode = {
  id: string;
  kind: StoryGraphNodeKind;
  label: string;
  level?: number;
  raceJob?: string;
  gender?: string;
  role?: string;
  trust?: number;
  known?: string[];
  description?: string;
  risk?: RiskBadge;
  dayPhase?: string;
  weather?: string[];
  moveDifficulty?: string | null;
  questDifficulty?: string;
  rewards?: { gold: number; exp: number };
};

export type StoryGraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
};

export type StoryGraphModel = {
  nodes: StoryGraphNode[];
  edges: StoryGraphEdge[];
  summary: string;
};

export const EMPTY_STORY_GRAPH: StoryGraphModel = {
  nodes: [],
  edges: [],
  summary: '스토리 데이터 없음',
};

type StoryGraphInput = {
  hero: Hero | null;
  subject: Subject | null;
  quest: Quest | null;
  place: Place | null;
};

export const KIND_LABEL: Record<StoryGraphNodeKind, string> = {
  hero: '주인공',
  place: '현재 위치',
  subject: '대상',
  quest: '퀘스트',
  location: '장소',
  target: '등장인물',
};

function slug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9가-힣_-]/g, '');
}

function nodeId(kind: StoryGraphNodeKind, label: string): string {
  return `${kind}:${slug(label) || 'unknown'}`;
}

function characterId(label: string): string {
  return `character:${slug(label) || 'unknown'}`;
}

function canonicalNodeId(kind: StoryGraphNodeKind, label: string): string {
  return kind === 'subject' || kind === 'target' ? characterId(label) : nodeId(kind, label);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function buildStoryGraph({ hero, subject, quest, place }: StoryGraphInput): StoryGraphModel {
  const nodes = new Map<string, StoryGraphNode>();
  const edges = new Map<string, StoryGraphEdge>();

  const addNode = (node: StoryGraphNode) => {
    nodes.set(node.id, node);
    return node.id;
  };

  const addEdge = (source: string | null, target: string | null, label: string) => {
    if (!source || !target || source === target) return;
    const id = `${source}->${target}:${label}`;
    edges.set(id, { id, source, target, label });
  };

  const heroId = hero
    ? addNode({
        id: nodeId('hero', hero.name),
        kind: 'hero',
        label: hero.name,
        level: hero.level,
        raceJob: hero.raceJob,
      })
    : null;

  const placeId = place
    ? addNode({
        id: nodeId('place', place.name),
        kind: 'place',
        label: place.name,
        description: place.description,
        risk: place.risk,
        dayPhase: place.dayPhase,
        weather: place.weather,
      })
    : null;

  const subjectId = subject
    ? addNode({
        id: characterId(subject.name),
        kind: 'subject',
        label: subject.name,
        level: subject.level,
        raceJob: subject.raceJob,
        gender: subject.gender,
        role: subject.role,
        trust: subject.trust,
        known: subject.known,
      })
    : null;

  const questId = quest
    ? addNode({
        id: nodeId('quest', quest.title),
        kind: 'quest',
        label: quest.title,
        questDifficulty: quest.difficulty,
        rewards: quest.rewards,
      })
    : null;

  addEdge(heroId, placeId, '현재 위치');
  addEdge(heroId, subjectId, '주시');
  addEdge(subjectId, placeId, '같은 장소');
  addEdge(heroId, questId, '진행 중');

  if (questId && subjectId && subject && quest?.giver === subject.name) {
    addEdge(subjectId, questId, '의뢰');
  }

  for (const surrounding of place?.surroundings ?? []) {
    const locationId = addNode({
      id: nodeId('location', surrounding.name),
      kind: 'location',
      label: surrounding.name,
      description: surrounding.blurb,
      risk: surrounding.risk,
      moveDifficulty: surrounding.difficulty ?? null,
    });
    addEdge(placeId, locationId, '이동');
  }

  for (const target of place?.targets ?? []) {
    const targetId =
      target.name === subject?.name && subjectId
        ? subjectId
        : addNode({
            id: characterId(target.name),
            kind: 'target',
            label: target.name,
            level: target.level,
            raceJob: target.raceJob,
            gender: target.gender,
            role: target.blurb,
            trust: target.trust,
          });
    addEdge(targetId, placeId, '등장');
  }

  const countByKind = Array.from(nodes.values()).reduce(
    (acc, node) => ({ ...acc, [node.kind]: acc[node.kind] + 1 }),
    {
      hero: 0,
      place: 0,
      subject: 0,
      quest: 0,
      location: 0,
      target: 0,
    } satisfies Record<StoryGraphNodeKind, number>,
  );

  const heroSummary = hero ? (hero.name === '주인공' ? '주인공' : `주인공 ${hero.name}`) : null;

  const summary = [
    heroSummary,
    place ? `현재 위치 ${place.name}` : null,
    quest ? `퀘스트 ${quest.title}` : null,
    `${KIND_LABEL.target} ${countByKind.target + countByKind.subject}`,
    `${KIND_LABEL.location} ${countByKind.location + countByKind.place}`,
  ]
    .filter(Boolean)
    .join(SEP);

  return {
    nodes: Array.from(nodes.values()),
    edges: Array.from(edges.values()),
    summary,
  };
}

export function mergeStoryGraphs(base: StoryGraphModel, next: StoryGraphModel): StoryGraphModel {
  if (base.nodes.length === 0 && base.edges.length === 0) return next;
  if (next.nodes.length === 0 && next.edges.length === 0) return base;

  const nextPlaceIds = new Set(next.nodes.filter((node) => node.kind === 'place').map((node) => node.id));
  const nextSubjectIds = new Set(next.nodes.filter((node) => node.kind === 'subject').map((node) => node.id));
  const nextByLabel = new Map<string, StoryGraphNode>();
  for (const n of next.nodes) {
    if (!nextByLabel.has(n.label)) nextByLabel.set(n.label, n);
  }

  const idRemap = new Map<string, string>();
  const nodes = new Map<string, StoryGraphNode>();
  for (const node of base.nodes) {
    const sameLabelInNext = nextByLabel.get(node.label);
    if (sameLabelInNext && sameLabelInNext.id !== node.id) {
      idRemap.set(node.id, sameLabelInNext.id);
      continue;
    }
    let demoted = node;
    if (node.kind === 'place' && !nextPlaceIds.has(node.id)) {
      demoted = { ...node, kind: 'location' };
    } else if (node.kind === 'subject' && !nextSubjectIds.has(node.id)) {
      demoted = { ...node, kind: 'target' };
    }
    const canon = canonicalNodeId(demoted.kind, demoted.label);
    if (canon !== node.id) {
      idRemap.set(node.id, canon);
      demoted = { ...demoted, id: canon };
    }
    nodes.set(demoted.id, demoted);
  }
  for (const node of next.nodes) {
    nodes.set(node.id, node);
  }

  const remap = (id: string) => idRemap.get(id) ?? id;
  const edges = new Map<string, StoryGraphEdge>();
  for (const edge of base.edges) {
    const source = remap(edge.source);
    const target = remap(edge.target);
    if (source === target) continue;
    const id = `${source}->${target}:${edge.label}`;
    edges.set(id, { id, source, target, label: edge.label });
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

export function normalizeStoryGraphPayload(
  payload: StoryGraphPayload | null,
): StoryGraphModel | null {
  if (!payload) return null;
  const nodes = payload.nodes.flatMap((raw): StoryGraphNode[] =>
    NODE_KIND.has(raw.kind as StoryGraphNodeKind)
      ? [{ id: raw.id, kind: raw.kind as StoryGraphNodeKind, label: raw.label }]
      : [],
  );
  const knownNodeIds = new Set(nodes.map((node) => node.id));
  const edges = payload.edges.filter(
    (e) => knownNodeIds.has(e.source) && knownNodeIds.has(e.target),
  );
  return { nodes, edges, summary: payload.summary };
}
