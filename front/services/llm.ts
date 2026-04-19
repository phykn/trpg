import { fetch } from 'expo/fetch';

import type { ChatChunk, ChatRequest } from '@/types/wire';

const BASE_URL = process.env.EXPO_PUBLIC_API_URL;
if (!BASE_URL) throw new Error('EXPO_PUBLIC_API_URL is not set');

export async function streamChat(
  body: ChatRequest,
  onChunk: (chunk: ChatChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ ...body, think: false }),
    signal,
  });
  if (!res.ok) throw new Error(`stream failed: HTTP ${res.status}`);
  const reader = res.body?.getReader();
  if (!reader) throw new Error('stream failed: response body is not readable');

  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const raw of lines) {
      const line = raw.trim();
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (payload === '[DONE]') return;
      onChunk(JSON.parse(payload) as ChatChunk);
    }
  }
}
