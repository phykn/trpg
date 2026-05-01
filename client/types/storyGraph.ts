import type { RiskBadge } from './domain';

export type StoryGraphNodeKind =
  | 'hero'
  | 'place'
  | 'subject'
  | 'quest'
  | 'location'
  | 'target';

// Flat shape with optional kind-specific fields. Producers (server
// `to_story_graph`) populate the fields for the kind they emit;
// consumers branch on kind and read the matching fields directly —
// never re-parse a combined display string.
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
