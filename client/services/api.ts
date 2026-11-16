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

// Always ends with done or error; a dropped connection counts as an error, so the caller can ask again.
export async function streamText(id: string, turn: number, onEvent: (event: TextEvent) => void): Promise<void> {
  let ended = false;
  const emit = (line: string) => {
    if (!line.trim()) return;
    const event = JSON.parse(line) as TextEvent;
    ended ||= event.type === 'done' || event.type === 'error';
    onEvent(event);
  };
  try {
    const response = await fetch(`${baseUrl}${gamePath(id)}/turns/${turn}/text`, { headers });
    if (!response.ok || !response.body) throw new ApiError(response.status, null);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      lines.forEach(emit);
      if (done) break;
    }
    emit(buffer);
  } catch {
    // ends as an error below
  }
  if (!ended) onEvent({ type: 'error' });
}
