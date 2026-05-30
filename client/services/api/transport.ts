import { fetch } from 'expo/fetch';

export type ApiFetchInit = {
  method?: 'GET' | 'POST';
  headers: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
};

export const BASE_URL = process.env.EXPO_PUBLIC_API_URL;
if (!BASE_URL) throw new Error('EXPO_PUBLIC_API_URL is not set');

const API_USER = process.env.EXPO_PUBLIC_API_USER;
if (!API_USER) throw new Error('EXPO_PUBLIC_API_USER is not set');

const API_PASS = process.env.EXPO_PUBLIC_API_PASS;
if (!API_PASS) throw new Error('EXPO_PUBLIC_API_PASS is not set');

const AUTH_HEADER = `Basic ${btoa(`${API_USER}:${API_PASS}`)}`;

const localTunnelHeaders: Record<string, string> = BASE_URL.includes('.loca.lt')
  ? { 'bypass-tunnel-reminder': 'true' }
  : {};

export const baseHeaders: Record<string, string> = {
  Authorization: AUTH_HEADER,
  ...localTunnelHeaders,
};

export const jsonHeaders: Record<string, string> = {
  ...baseHeaders,
  'Content-Type': 'application/json',
};

const REQUEST_TIMEOUT_MS = 90_000;

export async function requestJson<T>(
  operation: string,
  path: string,
  init: ApiFetchInit,
): Promise<T> {
  const res = await fetchWithTimeout(`${BASE_URL}${path}`, init);
  if (!res.ok) throw new Error(await httpError(operation, res));
  return (await res.json()) as T;
}

export async function fetchWithTimeout(
  url: string,
  init: ApiFetchInit,
): Promise<Response> {
  const { signal: callerSignal, ...fetchInit } = init;
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
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

export async function httpError(operation: string, res: Response): Promise<string> {
  const detail = await readErrorDetail(res);
  return displayError(operation, res.status, detail);
}

export function displayError(operation: string, status: number, detail: string): string {
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
