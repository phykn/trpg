import type { Hero, Place, Quest, Subject } from '@/types/domain';

export type StoryGraphNodeKind = 'hero' | 'place' | 'subject' | 'quest' | 'location' | 'target';

const NODE_KIND = new Set<StoryGraphNodeKind>([
  'hero',
  'place',
  'subject',
  'quest',
  'location',
  'target',
]);

export type StoryGraphNode = {
  id: string;
  kind: StoryGraphNodeKind;
  label: string;
  detail: string;
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

const KIND_LABEL: Record<StoryGraphNodeKind, string> = {
  hero: '주인공',
  place: '현재 위치',
  subject: '대상',
  quest: '퀘스트',
  location: '배경',
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

function shortList(items: string[], fallback = '정보 없음'): string {
  if (items.length === 0) return fallback;
  return items.slice(0, 3).join(', ');
}

function statLine(level: number, raceJob: string): string {
  return `Lv.${level} · ${raceJob}`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringField(source: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = source[key];
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number') return String(value);
  }
  return null;
}

function kindField(source: Record<string, unknown>): StoryGraphNodeKind {
  const raw = stringField(source, ['kind', 'type', 'entity_type', 'category']);
  if (raw === 'character') return 'target';
  if (raw === 'npc') return 'target';
  if (raw === 'player') return 'hero';
  if (raw && NODE_KIND.has(raw as StoryGraphNodeKind)) return raw as StoryGraphNodeKind;
  return 'target';
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
        detail: statLine(hero.level, hero.raceJob),
      })
    : null;

  const placeId = place
    ? addNode({
        id: nodeId('place', place.name),
        kind: 'place',
        label: place.name,
        detail: shortList([place.dayPhase, ...place.weather, place.risk.label].filter(Boolean)),
      })
    : null;

  const subjectId = subject
    ? addNode({
        id: characterId(subject.name),
        kind: 'subject',
        label: subject.name,
        detail: `${statLine(subject.level, subject.raceJob)} · ${subject.role}`,
      })
    : null;

  const questId = quest
    ? addNode({
        id: nodeId('quest', quest.title),
        kind: 'quest',
        label: quest.title,
        detail: `${quest.difficulty} · 보상 ${quest.rewards.gold}G/${quest.rewards.exp}EXP`,
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
      detail: surrounding.risk.label,
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
            detail: statLine(target.level, target.raceJob),
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
    .join(' · ');

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
  const nodes = new Map(base.nodes.map((node) => [node.id, node]));
  for (const [id, node] of nodes) {
    if (node.kind === 'place' && !nextPlaceIds.has(id)) {
      nodes.set(id, { ...node, kind: 'location' });
    }
    if (node.kind === 'subject' && !nextSubjectIds.has(id)) {
      nodes.set(id, { ...node, kind: 'target' });
    }
  }
  for (const node of next.nodes) {
    nodes.set(node.id, node);
  }

  const edges = new Map(base.edges.map((edge) => [edge.id, edge]));
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
    .map((node) => `${node.id}:${node.kind}:${node.label}:${node.detail}`)
    .sort()
    .join('|');
  const edges = graph.edges
    .map((edge) => `${edge.id}:${edge.source}:${edge.target}:${edge.label}`)
    .sort()
    .join('|');
  return `${graph.summary}::${nodes}::${edges}`;
}

export function normalizeStoryGraphPayload(payload: unknown): StoryGraphModel | null {
  const root = isObject(payload) && isObject(payload.graph) ? payload.graph : payload;
  if (!isObject(root) || !Array.isArray(root.nodes) || !Array.isArray(root.edges)) return null;

  const nodes = root.nodes.flatMap((raw): StoryGraphNode[] => {
    if (!isObject(raw)) return [];
    const id = stringField(raw, ['id', 'node_id', 'key']);
    const label = stringField(raw, ['label', 'name', 'title']);
    if (!id || !label) return [];
    const kind = kindField(raw);
    return [{
      id,
      kind,
      label,
      detail: stringField(raw, ['detail', 'description', 'summary', 'subtitle']) ?? KIND_LABEL[kind],
    }];
  });

  const knownNodeIds = new Set(nodes.map((node) => node.id));
  const edges = root.edges.flatMap((raw): StoryGraphEdge[] => {
    if (!isObject(raw)) return [];
    const source = stringField(raw, ['source', 'source_id', 'from', 'from_id']);
    const target = stringField(raw, ['target', 'target_id', 'to', 'to_id']);
    if (!source || !target || !knownNodeIds.has(source) || !knownNodeIds.has(target)) return [];
    const label = stringField(raw, ['label', 'type', 'relation']) ?? '관계';
    return [{
      id: stringField(raw, ['id']) ?? `${source}->${target}:${label}`,
      source,
      target,
      label,
    }];
  });

  return {
    nodes,
    edges,
    summary: stringField(root, ['summary', 'title']) ?? `서버 그래프 · ${nodes.length}N/${edges.length}E`,
  };
}
