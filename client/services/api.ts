import { fetch } from 'expo/fetch';

import { ko } from '@/locale/ko';
import type { GameCatalog, GameCommand, GameView } from './types';

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
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  try {
    const response = await fetch(`${baseUrl}/adventure${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok) {
      let message = ko.requestFailed;
      try {
        const payload = await response.json();
        if (typeof payload?.detail === 'string' && response.status !== 401) {
          message = payload.detail;
        }
      } catch { /* Non-JSON errors use the localized fallback. */ }
      throw new ApiError(response.status, message);
    }
    return await response.json() as T;
  } finally {
    clearTimeout(timeout);
  }
}

export const getCatalog = () => request<GameCatalog>('/catalog');
export const startGame = (name: string, role: string) =>
  request<GameView>('/start', { name, role });
export const loadGame = (id: string) =>
  request<GameView>(`/${encodeURIComponent(id)}`);
export const chooseOption = (id: string, command: GameCommand) =>
  request<GameView>(`/${encodeURIComponent(id)}/choose`, command);
