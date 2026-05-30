import type {
  StoryContractPreviewResponse,
  StoryContractResponse,
  StoryDebtResponse,
  StoryDebtWireResponse,
  StoryGraphResponse,
  StoryPatchEntriesResponse,
  StoryPatchEntriesWireResponse,
  StoryPatchLedgerEntry,
  StoryPatchLedgerEntryWire,
  StoryPatchPreviewProposal,
  StoryPatchPreviewResponse,
  StoryPatchPreviewWireResponse,
  StoryPromptReplayRequest,
  StoryPromptReplayResponse,
  StoryRollbackResponse,
  StoryRollbackWireResponse,
} from '@/services/wire';

import { baseHeaders, jsonHeaders, requestJson } from './transport';

export async function getStoryPatchEntries(gameId: string): Promise<StoryPatchEntriesResponse> {
  const payload = await requestJson<StoryPatchEntriesWireResponse>(
    'getStoryPatchEntries',
    `/session/${gameId}/story/patches`,
    {
      method: 'GET',
      headers: baseHeaders,
    },
  );
  return adaptStoryPatchEntries(payload);
}

export async function getStoryPatchTimeline(gameId: string): Promise<StoryPatchEntriesResponse> {
  const payload = await requestJson<StoryPatchEntriesWireResponse>(
    'getStoryPatchTimeline',
    `/session/${gameId}/story/timeline`,
    {
      method: 'GET',
      headers: baseHeaders,
    },
  );
  return adaptStoryPatchEntries(payload);
}

export async function getStoryDebt(gameId: string): Promise<StoryDebtResponse> {
  const payload = await requestJson<StoryDebtWireResponse>(
    'getStoryDebt',
    `/session/${gameId}/story/debt`,
    {
      method: 'GET',
      headers: baseHeaders,
    },
  );
  return {
    game_id: payload.game_id,
    debt: {
      unresolvedClues: payload.debt.unresolved_clues,
      orphanCharacters: payload.debt.orphan_characters,
      orphanItems: payload.debt.orphan_items,
      danglingQuestBeats: payload.debt.dangling_quest_beats,
    },
  };
}

export async function getStoryGraph(gameId: string): Promise<StoryGraphResponse> {
  return requestJson<StoryGraphResponse>(
    'getStoryGraph',
    `/session/${gameId}/story/dev/graph`,
    {
      method: 'GET',
      headers: baseHeaders,
    },
  );
}

export async function getStoryContract(gameId: string): Promise<StoryContractResponse> {
  return requestJson<StoryContractResponse>(
    'getStoryContract',
    `/session/${gameId}/story/dev/contract`,
    {
      method: 'GET',
      headers: baseHeaders,
    },
  );
}

export async function previewStoryContract(
  gameId: string,
  contract: Record<string, unknown>,
): Promise<StoryContractPreviewResponse> {
  return requestJson<StoryContractPreviewResponse>(
    'previewStoryContract',
    `/session/${gameId}/story/dev/preview_contract`,
    {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ contract }),
    },
  );
}

export async function updateStoryContract(
  gameId: string,
  contract: Record<string, unknown>,
): Promise<StoryContractResponse> {
  return requestJson<StoryContractResponse>(
    'updateStoryContract',
    `/session/${gameId}/story/dev/contract`,
    {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ contract }),
    },
  );
}

export async function rollbackStoryPatch(gameId: string): Promise<StoryRollbackResponse> {
  const payload = await requestJson<StoryRollbackWireResponse>(
    'rollbackStoryPatch',
    `/session/${gameId}/story/rollback`,
    {
      method: 'POST',
      headers: jsonHeaders,
    },
  );
  return {
    game_id: payload.game_id,
    entry: adaptStoryPatchEntry(payload.entry),
  };
}

export async function previewStoryPatch(
  gameId: string,
  proposal: StoryPatchPreviewProposal,
): Promise<StoryPatchPreviewResponse> {
  const payload = await requestJson<StoryPatchPreviewWireResponse>(
    'previewStoryPatch',
    `/session/${gameId}/story/dev/preview_patch`,
    {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ proposal }),
    },
  );
  return {
    game_id: payload.game_id,
    ok: payload.ok,
    reasons: payload.reasons,
    changedNodeIds: payload.changed_node_ids,
    changedEdgeIds: payload.changed_edge_ids,
  };
}

export async function replayStoryPrompt(
  gameId: string,
  body: StoryPromptReplayRequest,
): Promise<StoryPromptReplayResponse> {
  return requestJson<StoryPromptReplayResponse>(
    'replayStoryPrompt',
    `/session/${gameId}/story/dev/replay_prompt`,
    {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify(body),
    },
  );
}

function adaptStoryPatchEntries(
  payload: StoryPatchEntriesWireResponse,
): StoryPatchEntriesResponse {
  return {
    game_id: payload.game_id,
    entries: payload.entries.map(adaptStoryPatchEntry),
  };
}

function adaptStoryPatchEntry(entry: StoryPatchLedgerEntryWire): StoryPatchLedgerEntry {
  return {
    turn: entry.turn,
    status: entry.status,
    intentKind: entry.intent_kind,
    reason: entry.reason,
    patches: entry.patches,
    rejectedReasons: entry.rejected_reasons,
    changedNodeIds: entry.changed_node_ids,
    changedEdgeIds: entry.changed_edge_ids,
  };
}
