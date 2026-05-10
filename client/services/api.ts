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
  ProfileCard,
  SessionPayload,
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

export async function getGraphSessionById(gameId: string): Promise<SessionPayload | null> {
  const res = await fetch(`${BASE_URL}/session/${gameId}/graph/state`, { headers: baseHeaders });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`getGraphSessionById failed: HTTP ${res.status}`);
  const payload = (await res.json()) as GraphSessionPayload;
  const state = adaptGraphState(payload.state);
  return {
    game_id: payload.game_id,
    state,
    suggestions: deriveGraphSuggestions(payload.state),
  };
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
    status: payload.status,
    message: payload.message,
    suggestions: deriveGraphSuggestions(payload.state),
  };
}
