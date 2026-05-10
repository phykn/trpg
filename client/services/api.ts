import { fetch } from 'expo/fetch';

import { adaptGraphState, deriveGraphSuggestions } from './graphAdapter';
import type {
  ConfirmRequest,
  GraphAction,
  GraphActionClientResponse,
  GraphActionResponse,
  GraphLevelUpRequest,
  GraphSessionPayload,
  InitRequest,
  LevelUpPreviewResponse,
  LevelUpRequest,
  ProfileCard,
  RollRequest,
  SessionPayload,
  StreamEvent,
  TurnRequest,
} from '@/services/wire';

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
  const res = await fetch(`${BASE_URL}/version`, { headers: baseHeaders });
  if (!res.ok) throw new Error(`getVersion failed: HTTP ${res.status}`);
  return (await res.json()) as { sha: string };
}

export async function listProfiles(): Promise<ProfileCard[]> {
  const res = await fetch(`${BASE_URL}/profiles`, { headers: baseHeaders });
  if (!res.ok) throw new Error(`listProfiles failed: HTTP ${res.status}`);
  return (await res.json()) as ProfileCard[];
}

export async function getSessionById(gameId: string): Promise<SessionPayload | null> {
  const res = await fetch(`${BASE_URL}/session/${gameId}/state`, { headers: baseHeaders });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`getSessionById failed: HTTP ${res.status}`);
  const payload = (await res.json()) as SessionPayload;
  return { ...payload, runtime: 'legacy' };
}

export async function getGraphSessionById(gameId: string): Promise<SessionPayload | null> {
  const res = await fetch(`${BASE_URL}/session/${gameId}/graph/state`, { headers: baseHeaders });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`getGraphSessionById failed: HTTP ${res.status}`);
  const payload = (await res.json()) as GraphSessionPayload;
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    runtime: 'graph',
    suggestions: deriveGraphSuggestions(payload.state),
  };
}

export async function initSession(body: InitRequest): Promise<SessionPayload> {
  const res = await fetch(`${BASE_URL}/session/init`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`initSession failed: HTTP ${res.status}`);
  const payload = (await res.json()) as SessionPayload;
  return { ...payload, runtime: 'legacy' };
}

export async function initGraphSession(body: InitRequest): Promise<SessionPayload> {
  const res = await fetch(`${BASE_URL}/session/graph/init`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`initGraphSession failed: HTTP ${res.status}`);
  const payload = (await res.json()) as GraphSessionPayload;
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    runtime: 'graph',
    suggestions: deriveGraphSuggestions(payload.state),
  };
}

export async function sendGraphInput(
  gameId: string,
  playerInput: string,
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/input`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ player_input: playerInput, think: false }),
  });
  if (!res.ok) throw new Error(`sendGraphInput failed: HTTP ${res.status}`);
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function sendGraphAction(
  gameId: string,
  action: GraphAction,
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/turn`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`sendGraphAction failed: HTTP ${res.status}`);
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function sendGraphLevelUp(
  gameId: string,
  body: GraphLevelUpRequest,
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/level_up`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`sendGraphLevelUp failed: HTTP ${res.status}`);
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

export async function confirmGraphAction(
  gameId: string,
  body: ConfirmRequest,
): Promise<GraphActionClientResponse> {
  const res = await fetchWithTimeout(`${BASE_URL}/session/${gameId}/graph/confirm`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`confirmGraphAction failed: HTTP ${res.status}`);
  return adaptGraphActionResponse((await res.json()) as GraphActionResponse);
}

async function fetchWithTimeout(
  url: string,
  init: { method: 'POST'; headers: typeof jsonHeaders; body: string },
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), GRAPH_REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

function adaptGraphActionResponse(
  payload: GraphActionResponse,
): GraphActionClientResponse {
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    pendingConfirmation: state.pendingConfirmation ?? null,
    runtime: 'graph',
    status: payload.status,
    message: payload.message,
    suggestions: deriveGraphSuggestions(payload.state),
  };
}

async function streamSse(
  url: string,
  init: { method: 'POST'; body?: string },
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: init.method,
    headers: {
      ...jsonHeaders,
      Accept: 'text/event-stream',
    },
    body: init.body,
    signal,
  });
  if (!res.ok) {
    const detail = await res.text();
    const suffix = detail ? ` — ${detail.slice(0, 300)}` : '';
    throw new Error(`stream failed: HTTP ${res.status}${suffix}`);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error('stream failed: response body is not readable');

  const decoder = new TextDecoder();
  let buffer = '';

  const handleLine = (raw: string) => {
    const line = raw.trim();
    if (!line.startsWith('data:')) return;
    const payload = line.slice(5).trim();
    if (!payload) return;
    try {
      onEvent(JSON.parse(payload) as StreamEvent);
    } catch (e) {
      console.warn('streamSse: malformed chunk skipped', e);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const raw of lines) handleLine(raw);
  }
  if (buffer) handleLine(buffer);
}

export function streamTurn(
  gameId: string,
  body: TurnRequest,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    `${BASE_URL}/session/${gameId}/turn`,
    { method: 'POST', body: JSON.stringify(body) },
    onEvent,
    signal,
  );
}

export function streamRoll(
  gameId: string,
  body: RollRequest,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    `${BASE_URL}/session/${gameId}/roll`,
    { method: 'POST', body: JSON.stringify(body) },
    onEvent,
    signal,
  );
}

export function streamIntro(
  gameId: string,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    `${BASE_URL}/session/${gameId}/intro`,
    { method: 'POST' },
    onEvent,
    signal,
  );
}

export async function getLevelUpPreview(
  gameId: string,
  signal?: AbortSignal,
): Promise<LevelUpPreviewResponse> {
  const res = await fetch(`${BASE_URL}/session/${gameId}/level_up_preview`, {
    headers: baseHeaders,
    signal,
  });
  if (!res.ok) throw new Error(`getLevelUpPreview failed: HTTP ${res.status}`);
  return (await res.json()) as LevelUpPreviewResponse;
}

export function streamLevelUp(
  gameId: string,
  body: LevelUpRequest,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(
    `${BASE_URL}/session/${gameId}/level_up`,
    { method: 'POST', body: JSON.stringify(body) },
    onEvent,
    signal,
  );
}
