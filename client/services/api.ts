import { fetch } from 'expo/fetch';

import type {
  InitRequest,
  ProfileCard,
  RollRequest,
  SessionPayload,
  StreamEvent,
  TurnRequest,
} from '@/types/wire';

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

export async function listProfiles(): Promise<ProfileCard[]> {
  const res = await fetch(`${BASE_URL}/profiles`, { headers: baseHeaders });
  if (!res.ok) throw new Error(`listProfiles failed: HTTP ${res.status}`);
  return (await res.json()) as ProfileCard[];
}

export async function getSessionById(gameId: string): Promise<SessionPayload | null> {
  const res = await fetch(`${BASE_URL}/session/${gameId}/state`, { headers: baseHeaders });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`getSessionById failed: HTTP ${res.status}`);
  return (await res.json()) as SessionPayload;
}

export async function getSessionGraphById(gameId: string): Promise<unknown | null> {
  const res = await fetch(`${BASE_URL}/session/${gameId}/graph`, { headers: baseHeaders });
  if (res.status === 404 || res.status === 405) return null;
  if (!res.ok) throw new Error(`getSessionGraphById failed: HTTP ${res.status}`);
  return await res.json();
}

export async function initSession(body: InitRequest): Promise<SessionPayload> {
  const res = await fetch(`${BASE_URL}/session/init`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`initSession failed: HTTP ${res.status}`);
  return (await res.json()) as SessionPayload;
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
