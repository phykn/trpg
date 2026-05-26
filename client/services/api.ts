import { fetch } from 'expo/fetch';

import { adaptGraphState } from './graphAdapter';
import { normalizeGraphSuggestion } from './suggestions';
import type {
  CombatCommand,
  ConfirmRequest,
  GraphAction,
  GraphActionClientResponse,
  GraphActionResponse,
  GraphSuggestion,
  GraphLevelUpChoice,
  GraphLevelUpChoicesResponse,
  GraphLevelUpRequest,
  GraphRollRequest,
  GraphResultOutcome,
  GraphSessionPayload,
  InitRequest,
  ProfileCard,
  SessionPayload,
  StoryDebtResponse,
  StoryDebtWireResponse,
  StoryContractPreviewResponse,
  StoryContractResponse,
  StoryGraphResponse,
  StoryPatchEntriesResponse,
  StoryPatchEntriesWireResponse,
  StoryPatchPreviewProposal,
  StoryPatchPreviewResponse,
  StoryPatchPreviewWireResponse,
  StoryPromptReplayRequest,
  StoryPromptReplayResponse,
  StoryPatchLedgerEntry,
  StoryPatchLedgerEntryWire,
  StoryRollbackResponse,
  StoryRollbackWireResponse,
  SuggestionChip,
} from '@/services/wire';

type ApiRequestOptions = {
  signal?: AbortSignal;
  onResult?: (response: GraphActionClientResponse) => void;
  onNarrationDelta?: (text: string, outcome: GraphResultOutcome) => void;
};

const BASE_URL = process.env.EXPO_PUBLIC_API_URL;
if (!BASE_URL) throw new Error('EXPO_PUBLIC_API_URL is not set');

const API_USER = process.env.EXPO_PUBLIC_API_USER;
if (!API_USER) throw new Error('EXPO_PUBLIC_API_USER is not set');

const API_PASS = process.env.EXPO_PUBLIC_API_PASS;
if (!API_PASS) throw new Error('EXPO_PUBLIC_API_PASS is not set');

const AUTH_HEADER = `Basic ${btoa(`${API_USER}:${API_PASS}`)}`;

const localTunnelHeaders: Record<string, string> = BASE_URL.includes('.loca.lt')
  ? { 'bypass-tunnel-reminder': 'true' }
  : {};

const baseHeaders: Record<string, string> = {
  Authorization: AUTH_HEADER,
  ...localTunnelHeaders,
};
const jsonHeaders: Record<string, string> = {
  ...baseHeaders,
  'Content-Type': 'application/json',
};
const GRAPH_REQUEST_TIMEOUT_MS = 90_000;

export async function getVersion(): Promise<{ sha: string }> {
  return requestJson<{ sha: string }>('getVersion', '/version', { headers: baseHeaders });
}

export async function listProfiles(): Promise<ProfileCard[]> {
  return requestJson<ProfileCard[]>('listProfiles', '/profiles', { headers: baseHeaders });
}

export async function getGraphSessionById(gameId: string): Promise<SessionPayload | null> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/state`, {
    headers: baseHeaders,
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await httpError('getGraphSessionById', res));
  const payload = (await res.json()) as GraphSessionPayload;
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    suggestions: adaptSuggestions(payload.suggestions),
  };
}

export async function initGraphSession(body: InitRequest): Promise<SessionPayload> {
  const payload = await requestJson<GraphSessionPayload>('initGraphSession', '/session/graph/init', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    suggestions: adaptSuggestions(payload.suggestions),
  };
}

export async function requestGraphIntro(
  gameId: string,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  if (typeof TextDecoder === 'undefined') {
    return requestGraphActionPlain('requestGraphIntro', `/session/${gameId}/graph/intro`, undefined, options);
  }
  const streamResponse = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/intro/stream`, {
    method: 'POST',
    headers: jsonHeaders,
    signal: options.signal,
  });
  if (streamResponse.status !== 404) {
    if (!streamResponse.ok) throw new Error(await httpError('requestGraphIntro', streamResponse));
    return readGraphActionStream('requestGraphIntro', streamResponse, options);
  }
  return requestGraphActionPlain('requestGraphIntro', `/session/${gameId}/graph/intro`, undefined, options);
}

export async function sendGraphInput(
  gameId: string,
  playerInput: string,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  return requestGraphActionWithOptionalStream(
    'sendGraphInput',
    `/session/${gameId}/graph/input/stream`,
    `/session/${gameId}/graph/input`,
    { player_input: playerInput },
    options,
  );
}

async function requestGraphActionWithOptionalStream(
  operation: string,
  streamPath: string,
  plainPath: string,
  bodyPayload: object,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  if (typeof TextDecoder === 'undefined') {
    return requestGraphActionPlain(operation, plainPath, bodyPayload, options);
  }
  const body = JSON.stringify(bodyPayload);
  const res = await fetchWithTimeout(`${BASE_URL}${streamPath}`, {
    method: 'POST',
    headers: jsonHeaders,
    body,
    signal: options.signal,
  });
  if (res.status === 404) {
    return requestGraphActionPlain(operation, plainPath, bodyPayload, options);
  }
  if (!res.ok) throw new Error(await httpError(operation, res));
  return readGraphActionStream(operation, res, options);
}

async function requestGraphActionPlain(
  operation: string,
  path: string,
  bodyPayload: object | undefined,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: jsonHeaders,
    body: bodyPayload === undefined ? undefined : JSON.stringify(bodyPayload),
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError(operation, res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

type GraphInputStreamEvent =
  | { type: 'result'; payload?: unknown }
  | { type: 'narration_delta'; text?: unknown }
  | { type: 'final'; payload?: unknown }
  | { type: 'error'; status?: unknown; message?: unknown };

async function readGraphActionStream(
  operation: string,
  res: Response,
  options: ApiRequestOptions,
): Promise<GraphActionClientResponse> {
  const reader = res.body?.getReader?.();
  let finalPayload: GraphActionResponse | null = null;
  let resultOutcome: GraphResultOutcome = 'neutral';
  const consumeLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const event = JSON.parse(trimmed) as GraphInputStreamEvent;
    if (event.type === 'result') {
      const payload = event.payload as GraphActionResponse;
      const response = adaptGraphActionResponse(payload);
      resultOutcome = response.outcome;
      options.onResult?.(response);
      return;
    }
    if (event.type === 'narration_delta') {
      if (typeof event.text === 'string' && event.text) {
        options.onNarrationDelta?.(event.text, resultOutcome);
      }
      return;
    }
    if (event.type === 'final') {
      finalPayload = event.payload as GraphActionResponse;
      return;
    }
    if (event.type === 'error') {
      const status = typeof event.status === 'number' ? event.status : res.status;
      const detail = typeof event.message === 'string' ? event.message : 'stream error';
      throw new Error(displayError(operation, status, detail));
    }
  };

  if (reader) {
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? '';
        for (const line of lines) consumeLine(line);
      }
      buffer += decoder.decode();
      consumeLine(buffer);
    } finally {
      reader.releaseLock?.();
    }
  } else {
    const text = await res.text();
    for (const line of text.split(/\r?\n/)) consumeLine(line);
  }

  if (!finalPayload) {
    throw new Error(`${operation} failed: stream ended without final payload`);
  }
  return adaptGraphActionResponse(finalPayload);
}

export async function sendGraphAction(
  gameId: string,
  action: GraphAction,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  return requestGraphActionWithOptionalStream(
    'sendGraphAction',
    `/session/${gameId}/graph/turn/stream`,
    `/session/${gameId}/graph/turn`,
    { action },
    options,
  );
}

export async function sendGraphCombatCommand(
  gameId: string,
  command: CombatCommand,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  return requestGraphActionWithOptionalStream(
    'sendGraphCombatCommand',
    `/session/${gameId}/graph/combat/stream`,
    `/session/${gameId}/graph/combat`,
    command,
    options,
  );
}

export async function sendGraphLevelUp(
  gameId: string,
  body: GraphLevelUpRequest,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/level_up`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError('sendGraphLevelUp', res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function getGraphLevelUpOptions(
  gameId: string,
  options: ApiRequestOptions = {},
): Promise<GraphLevelUpChoice[]> {
  const payload = await requestJson<GraphLevelUpChoicesResponse>(
    'getGraphLevelUpOptions',
    `/session/${gameId}/graph/level_up/options`,
    {
      method: 'GET',
      headers: baseHeaders,
      signal: options.signal,
    },
  );
  return payload.choices;
}

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

export async function confirmGraphAction(
  gameId: string,
  body: ConfirmRequest,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  return requestGraphActionWithOptionalStream(
    'confirmGraphAction',
    `/session/${gameId}/graph/confirm/stream`,
    `/session/${gameId}/graph/confirm`,
    body,
    options,
  );
}

export async function rollGraphPending(
  gameId: string,
  body: GraphRollRequest,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  return requestGraphActionWithOptionalStream(
    'rollGraphPending',
    `/session/${gameId}/graph/roll/stream`,
    `/session/${gameId}/graph/roll`,
    body,
    options,
  );
}

type ApiFetchInit = {
  method?: 'GET' | 'POST';
  headers: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
};

async function requestJson<T>(
  operation: string,
  path: string,
  init: ApiFetchInit,
): Promise<T> {
  const res = await fetchWithTimeout(`${BASE_URL}${path}`, init);
  if (!res.ok) throw new Error(await httpError(operation, res));
  return (await res.json()) as T;
}

async function fetchWithTimeout(
  url: string,
  init: ApiFetchInit,
): Promise<Response> {
  const { signal: callerSignal, ...fetchInit } = init;
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timeout = setTimeout(() => controller.abort(), GRAPH_REQUEST_TIMEOUT_MS);
  if (callerSignal?.aborted) {
    abort();
  } else {
    callerSignal?.addEventListener('abort', abort, { once: true });
  }
  try {
    return await fetch(url, { ...fetchInit, signal: controller.signal });
  } finally {
    callerSignal?.removeEventListener('abort', abort);
    clearTimeout(timeout);
  }
}

async function httpError(operation: string, res: Response): Promise<string> {
  const detail = await readErrorDetail(res);
  return displayError(operation, res.status, detail);
}

function displayError(operation: string, status: number, detail: string): string {
  return detail || `${operation} failed: HTTP ${status}`;
}

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map(String).join(', ');
    if (typeof body?.message === 'string') return body.message;
  } catch {
    try {
      return (await res.text()).trim();
    } catch {
      return '';
    }
  }
  return '';
}

function adaptGraphActionResponse(
  payload: GraphActionResponse,
): GraphActionClientResponse {
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    pendingConfirmation: state.pendingConfirmation ?? null,
    pendingRoll: state.pendingRoll ?? null,
    status: payload.status,
    outcome: payload.outcome ?? 'neutral',
    message: payload.message,
    suggestions: adaptSuggestions(payload.suggestions),
  };
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

function adaptSuggestions(suggestions: GraphSuggestion[] | undefined): SuggestionChip[] {
  if (!Array.isArray(suggestions)) {
    return [];
  }
  const clean = Array.isArray(suggestions)
    ? suggestions.flatMap((suggestion) => {
        const normalized = normalizeGraphSuggestion(suggestion);
        return normalized ? [normalized] : [];
      })
    : [];
  return clean;
}
