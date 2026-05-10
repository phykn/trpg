import { fetch } from 'expo/fetch';

import { adaptGraphState, deriveGraphSuggestions } from './graphAdapter';
import type {
  ConfirmRequest,
  GraphAction,
  GraphActionClientResponse,
  GraphActionResponse,
  GraphLevelUpRequest,
  GraphRollRequest,
  GraphSessionPayload,
  InitRequest,
  ProfileCard,
  SessionPayload,
} from '@/services/wire';

type ApiRequestOptions = {
  signal?: AbortSignal;
};

const BASE_URL = process.env.EXPO_PUBLIC_API_URL;
if (!BASE_URL) throw new Error('EXPO_PUBLIC_API_URL is not set');

const API_USER = process.env.EXPO_PUBLIC_API_USER;
if (!API_USER) throw new Error('EXPO_PUBLIC_API_USER is not set');

const API_PASS = process.env.EXPO_PUBLIC_API_PASS;
if (!API_PASS) throw new Error('EXPO_PUBLIC_API_PASS is not set');

const AUTH_HEADER = `Basic ${btoa(`${API_USER}:${API_PASS}`)}`;

const baseHeaders = {
  Authorization: AUTH_HEADER,
};
const jsonHeaders = {
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
    suggestions: deriveGraphSuggestions(payload.state),
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
    suggestions: deriveGraphSuggestions(payload.state),
  };
}

export async function requestGraphIntro(
  gameId: string,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/intro`, {
    method: 'POST',
    headers: jsonHeaders,
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError('requestGraphIntro', res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function sendGraphInput(
  gameId: string,
  playerInput: string,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/input`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ player_input: playerInput, think: false }),
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError('sendGraphInput', res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function sendGraphAction(
  gameId: string,
  action: GraphAction,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/turn`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ action }),
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError('sendGraphAction', res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
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

export async function confirmGraphAction(
  gameId: string,
  body: ConfirmRequest,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/confirm`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError('confirmGraphAction', res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function rollGraphPending(
  gameId: string,
  body: GraphRollRequest,
  options: ApiRequestOptions = {},
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/roll`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
    signal: options.signal,
  });
  if (!res.ok) throw new Error(await httpError('rollGraphPending', res));
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

type ApiFetchInit = {
  method?: 'GET' | 'POST';
  headers: typeof baseHeaders | typeof jsonHeaders;
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
  return `${operation} failed: HTTP ${res.status}${detail ? ` (${detail})` : ''}`;
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
    message: payload.message,
    suggestions: deriveGraphSuggestions(payload.state),
  };
}
