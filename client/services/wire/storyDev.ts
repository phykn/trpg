import type { GraphAction } from './actions';

export type StoryPatchLedgerStatus = 'accepted' | 'rejected' | 'skipped' | 'rolled_back';

export type StoryPatchLedgerIntent = 'none' | 'memory_candidate' | 'clue_candidate' | 'both';

export type StoryPatchLedgerEntryWire = {
  turn: number;
  status: StoryPatchLedgerStatus;
  intent_kind: StoryPatchLedgerIntent;
  reason: string;
  patches: Record<string, unknown>[];
  rejected_reasons: string[];
  changed_node_ids: string[];
  changed_edge_ids: string[];
};

export type StoryPatchLedgerEntry = {
  turn: number;
  status: StoryPatchLedgerStatus;
  intentKind: StoryPatchLedgerIntent;
  reason: string;
  patches: Record<string, unknown>[];
  rejectedReasons: string[];
  changedNodeIds: string[];
  changedEdgeIds: string[];
};

export type StoryPatchEntriesWireResponse = {
  game_id: string;
  entries: StoryPatchLedgerEntryWire[];
};

export type StoryPatchEntriesResponse = {
  game_id: string;
  entries: StoryPatchLedgerEntry[];
};

export type StoryDebtEntryWire = {
  id: string;
  title: string;
  turn?: number | null;
  reason: string;
};

export type StoryDebtEntry = {
  id: string;
  title: string;
  turn?: number | null;
  reason: string;
};

export type StoryDebtWire = {
  unresolved_clues: StoryDebtEntryWire[];
  orphan_characters: StoryDebtEntryWire[];
  orphan_items: StoryDebtEntryWire[];
  dangling_quest_beats: StoryDebtEntryWire[];
};

export type StoryDebt = {
  unresolvedClues: StoryDebtEntry[];
  orphanCharacters: StoryDebtEntry[];
  orphanItems: StoryDebtEntry[];
  danglingQuestBeats: StoryDebtEntry[];
};

export type StoryDebtWireResponse = {
  game_id: string;
  debt: StoryDebtWire;
};

export type StoryDebtResponse = {
  game_id: string;
  debt: StoryDebt;
};

export type StoryGraphNode = {
  id: string;
  type: string;
  properties?: Record<string, unknown>;
};

export type StoryGraphEdge = {
  id: string;
  type: string;
  from: string;
  to: string;
  properties?: Record<string, unknown>;
};

export type StoryGraph = {
  nodes: Record<string, StoryGraphNode>;
  edges: Record<string, StoryGraphEdge>;
};

export type StoryGraphResponse = {
  game_id: string;
  graph: StoryGraph;
};

export type StoryContract = {
  id: string;
  world: {
    title: string;
    locale: 'ko';
  };
  fixed: string[];
  forbid: string[];
  tone: {
    register: string;
    person: 'second';
  };
  budgets: {
    patches_per_turn: number;
    new_terms_per_turn: number;
  };
  allowed_ops: string[];
  stability_defaults: Record<string, string>;
};

export type StoryContractResponse = {
  game_id: string;
  contract: StoryContract;
};

export type StoryContractPreviewResponse = {
  game_id: string;
  ok: boolean;
  reasons: string[];
  contract?: StoryContract | null;
};

export type StoryRollbackWireResponse = {
  game_id: string;
  entry: StoryPatchLedgerEntryWire;
};

export type StoryRollbackResponse = {
  game_id: string;
  entry: StoryPatchLedgerEntry;
};

export type StoryPatchPreviewProposal = {
  reason: string;
  patches: Record<string, unknown>[];
  narration_brief?: string | null;
};

export type StoryPatchPreviewWireResponse = {
  game_id: string;
  ok: boolean;
  reasons: string[];
  changed_node_ids: string[];
  changed_edge_ids: string[];
};

export type StoryPatchPreviewResponse = {
  game_id: string;
  ok: boolean;
  reasons: string[];
  changedNodeIds: string[];
  changedEdgeIds: string[];
};

export type StoryPromptReplayRequest = {
  player_input: string;
  action: GraphAction;
};

export type StoryPromptReplayResponse = {
  game_id: string;
  agent: 'story_write';
  intent: Record<string, unknown>;
  system_prompt: string;
  user_payload: Record<string, unknown>;
};
