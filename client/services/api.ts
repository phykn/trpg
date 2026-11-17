import type { CommandBody, GameView, PastTurn, Story, TextEvent, TurnResult } from './types';

const baseUrl = process.env.EXPO_PUBLIC_API_URL;
const user = process.env.EXPO_PUBLIC_API_USER;
const pass = process.env.EXPO_PUBLIC_API_PASS;
if (!baseUrl || !user || !pass) {
  throw new Error('Set EXPO_PUBLIC_API_URL, EXPO_PUBLIC_API_USER and EXPO_PUBLIC_API_PASS');
}
const headers = { Authorization: `Basic ${btoa(`${user}:${pass}`)}`, 'Content-Type': 'application/json' };

// A 409 carries the game as it now is (engine/02 6절).
export class ApiError extends Error {
  constructor(public status: number, public view: GameView | null) {
    super(`HTTP ${status}`);
  }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { view?: GameView };
    throw new ApiError(response.status, payload.view ?? null);
  }
  return await response.json() as T;
}

const gamePath = (id: string) => `/games/${encodeURIComponent(id)}`;

export const getStories = () => request<Story[]>('/stories');
export const createGame = (requestId: string, story: string) =>
  request<{ game: string; view: GameView }>('/games', { request_id: requestId, story });
export const getGame = (id: string) => request<GameView>(gamePath(id));
export const getTurns = (id: string, from: number) => request<PastTurn[]>(`${gamePath(id)}/turns?from=${from}`);
export const sendCommand = (id: string, requestId: string, revision: number, body: CommandBody) =>
  request<TurnResult>(`${gamePath(id)}/commands`, { request_id: requestId, revision, ...body });

// It polls rather than reading one stream: the phone's quick tunnel holds a stream back until it ends.
export async function streamText(id: string, turn: number, signal: AbortSignal,
  onEvent: (event: Extract<TextEvent, { slot: number }>) => void): Promise<boolean> {
  let after = 0;
  try {
    while (!signal.aborted) {
      const response = await fetch(`${baseUrl}${gamePath(id)}/turns/${turn}/text/poll?after=${after}`, { headers, signal });
      if (!response.ok) return false;
      const polled = (await response.json()) as { events: TextEvent[]; next: number };
      for (const event of polled.events) {
        if (signal.aborted || event.type === 'error') return false;
        if (event.type === 'done') return true;
        if ('slot' in event) onEvent(event);
      }
      after = polled.next;
    }
  } catch {
    return false;
  }
  return false;
}
