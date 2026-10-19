import { fetch } from 'expo/fetch';

import type { CommandBody, CommandResult, Creation, GameView, NarrationEvent, Story } from './types';

const baseUrl = process.env.EXPO_PUBLIC_API_URL;
const user = process.env.EXPO_PUBLIC_API_USER;
const pass = process.env.EXPO_PUBLIC_API_PASS;
if (!baseUrl || !user || !pass) {
  throw new Error('Set EXPO_PUBLIC_API_URL, EXPO_PUBLIC_API_USER and EXPO_PUBLIC_API_PASS');
}
const headers = {
  Authorization: `Basic ${btoa(`${user}:${pass}`)}`,
  'Content-Type': 'application/json',
};

export class ApiError extends Error {
  constructor(public status: number, public view: GameView | null, public reason: string | null) {
    super(`HTTP ${status}`);
  }
}

async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let payload: { view?: GameView; reason?: string } = {};
    try { payload = await response.json() as typeof payload; } catch { /* a body that is not JSON */ }
    throw new ApiError(response.status, payload.view ?? null, payload.reason ?? null);
  }
  return await response.json() as T;
}

const game = (id: string) => `/games/${encodeURIComponent(id)}`;

export const getStories = () => request<Story[]>('/stories');
export const createGame = (requestId: string, story: string, creation: Creation, signal?: AbortSignal) =>
  request<{ game_id: string; view: GameView }>('/games', { request_id: requestId, story, creation }, signal);
export const getGame = (id: string) => request<GameView>(game(id));
export const sendCommand = (id: string, requestId: string, revision: number, body: CommandBody, signal?: AbortSignal) =>
  request<CommandResult>(`${game(id)}/commands`, { request_id: requestId, revision, ...body }, signal);

export class LineReader {
  private buffer = '';

  feed(chunk: string): NarrationEvent[] {
    this.buffer += chunk;
    const out: NarrationEvent[] = [];
    let newline = this.buffer.indexOf('\n');
    while (newline >= 0) {
      const line = this.buffer.slice(0, newline).trim();
      this.buffer = this.buffer.slice(newline + 1);
      if (line) out.push(JSON.parse(line) as NarrationEvent);
      newline = this.buffer.indexOf('\n');
    }
    return out;
  }

  end(): NarrationEvent[] {
    const rest = this.buffer.trim();
    this.buffer = '';
    return rest ? [JSON.parse(rest) as NarrationEvent] : [];
  }
}

export async function stream(path: string, onEvent: (event: NarrationEvent) => void): Promise<void> {
  let ended = false;
  const emit = (e: NarrationEvent) => {
    if (e.type === 'error' || e.type === 'done') ended = true;
    onEvent(e);
  };
  try {
    const response = await fetch(`${baseUrl}${path}`, { headers });
    if (!response.ok || !response.body) throw new ApiError(response.status, null, null);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const lines = new LineReader();
    for (;;) {
      const { done, value } = await reader.read();
      lines.feed(decoder.decode(value ?? new Uint8Array(), { stream: !done })).forEach(emit);
      if (done) break;
    }
    lines.end().forEach(emit);
  } catch {
    if (!ended) emit({ type: 'error' });
    return;
  }
  if (!ended) emit({ type: 'error' });
}

export const narrationPath = (id: string, n: number) => `${game(id)}/turns/${n}/narration`;
export const recapPath = (id: string, k: number) => `${game(id)}/chapters/${k}/recap`;
