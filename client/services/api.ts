import { fetch } from 'expo/fetch';

import { ko } from '@/locale/ko';
import type { ActResult, Creation, Envelope, GameView, NarrationEvent, StoryCard } from './types';

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
const REQUEST_MS = 15_000;
const NARRATION_IDLE_MS = 30_000;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function failure(response: { status: number; json: () => Promise<unknown> }): Promise<ApiError> {
  let message = ko.requestFailed;
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload?.detail === 'string' && response.status !== 401) message = payload.detail;
  } catch { /* Non-JSON errors use the localized fallback. */ }
  return new ApiError(response.status, message);
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_MS);
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) throw await failure(response);
    return await response.json() as T;
  } finally {
    clearTimeout(timeout);
  }
}

export const getCatalog = () => request<StoryCard[]>('/catalog');
export const startGame = (story: string, creation?: Creation) =>
  request<GameView>('/games', { story, ...creation });
export const loadGame = (id: string) => request<GameView>(`/games/${encodeURIComponent(id)}`);
export const act = (id: string, envelope: Envelope) =>
  request<ActResult>(`/games/${encodeURIComponent(id)}/act`, envelope);

/** Read the newline-delimited narration events of one turn; resolves when the stream ends. */
export async function streamNarration(id: string, turn: number, onEvent: (event: NarrationEvent) => void) {
  const controller = new AbortController();
  let idle = setTimeout(() => controller.abort(), NARRATION_IDLE_MS);
  try {
    const response = await fetch(`${baseUrl}/games/${encodeURIComponent(id)}/turns/${turn}/narration`, {
      headers, signal: controller.signal,
    });
    if (!response.ok || !response.body) throw await failure(response);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      clearTimeout(idle);
      idle = setTimeout(() => controller.abort(), NARRATION_IDLE_MS);
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let newline = buffer.indexOf('\n');
      while (newline >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (line) onEvent(JSON.parse(line) as NarrationEvent);
        newline = buffer.indexOf('\n');
      }
      if (done) break;
    }
  } finally {
    clearTimeout(idle);
  }
}
