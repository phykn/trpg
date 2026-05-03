import type { Tone } from '@/components/ui';

export type RiskBadge = { label: string; tone: Tone };

export type StoryGraphNodeKind =
  | 'hero'
  | 'place'
  | 'subject'
  | 'quest'
  | 'location'
  | 'target';

export type NodeStatus =
  | 'current'
  | 'engaged'
  | 'reachable_move'
  | 'reachable_meet'
  | 'unreachable_move'
  | 'unreachable_meet';

export type EdgeKind =
  | 'current_pin'
  | 'observe'
  | 'progress'
  | 'move'
  | 'meet'
  | 'quest_giver'
  | 'quest_target';

// Discriminated by `kind`; adding a field to a builder without updating the matching variant is a compile error.
type BaseNode = { id: string; label: string };

type CharacterFields = {
  level: number;
  raceJob: string;
  gender: string;
  role: string;
  alive: boolean;
};

export type HeroNode = BaseNode & CharacterFields & {
  kind: 'hero';
  status: null;
  reachable: true;
  known: string[];
};

export type SubjectNode = BaseNode & CharacterFields & {
  kind: 'subject';
  status: 'engaged';
  reachable: true;
  trust: number;
  known: string[];
};

export type TargetNode = BaseNode & CharacterFields & {
  kind: 'target';
  status: 'reachable_meet' | 'unreachable_meet';
  reachable: boolean;
  trust: number;
};

export type PlaceNode = BaseNode & {
  kind: 'place';
  status: 'current';
  reachable: true;
  description: string;
  risk: RiskBadge;
  dayPhase: string;
  weather: string[];
};

export type LocationNode = BaseNode & {
  kind: 'location';
  status: 'reachable_move' | 'unreachable_move';
  reachable: boolean;
  description: string;
  risk: RiskBadge;
  moveDifficulty: string | null;
};

export type QuestNode = BaseNode & {
  kind: 'quest';
  status: null;
  reachable: true;
  questDifficulty: string;
  rewards: { gold: number; exp: number };
  giver: string;
  goals: string[];
  summary: string;
};

export type StoryGraphNode =
  | HeroNode
  | PlaceNode
  | LocationNode
  | SubjectNode
  | TargetNode
  | QuestNode;

export type StoryGraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  kind?: EdgeKind;
};

export type StoryGraphModel = {
  nodes: StoryGraphNode[];
  edges: StoryGraphEdge[];
  summary: string;
};

export type PlaceSurrounding = {
  name: string;
  blurb: string;
  difficulty: string | null;
  risk: RiskBadge;
};

export type PlaceTarget = {
  name: string;
  level: number;
  raceJob: string;
  gender: string;
  blurb: string;
  trust: number;
};

export type Place = {
  name: string;
  description: string;
  dayPhase: string;
  weather: string[];
  features: string[];
  surroundings: PlaceSurrounding[];
  targets: PlaceTarget[];
  risk: RiskBadge;
};
