// LLM 서버 스모크 테스트. 백엔드 연결 시 services/로 옮기고 이 파일은 제거.
//
// 호스트 주의: iOS 시뮬레이터는 localhost 가능, Android 에뮬레이터는 10.0.2.2,
// 실기기(터널)는 개발 머신 LAN IP. 필요 시 EXPO_PUBLIC_LLM_URL 로 덮어쓴다.

const BASE_URL = process.env.EXPO_PUBLIC_LLM_URL ?? 'http://localhost:8001';

export type ChatRequest = {
  system?: string;
  query: string;
  think?: boolean;
};

export type ChatChunk = {
  think: string | null;
  answer: string | null;
};

export async function testComplete(body: ChatRequest): Promise<ChatChunk> {
  const res = await fetch(`${BASE_URL}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ think: true, ...body }),
  });
  if (!res.ok) throw new Error(`complete failed: HTTP ${res.status}`);
  return res.json();
}

export async function testStream(
  body: ChatRequest,
  onChunk: (chunk: ChatChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ think: true, ...body }),
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

// 콘솔에서 바로 돌려볼 수 있는 한 줄 진단. 개발 중 아무 컴포넌트에서 호출.
export async function smokeTest(query = '안녕하세요. 한 문장으로 답해주세요.'): Promise<void> {
  console.log('[llm-test] base =', BASE_URL);
  try {
    const full = await testComplete({ query, think: false });
    console.log('[llm-test] /complete answer:', full.answer);
  } catch (err) {
    console.error('[llm-test] /complete error:', err);
    return;
  }
  try {
    const parts: string[] = [];
    await testStream({ query, think: false }, (chunk) => {
      if (chunk.answer) parts.push(chunk.answer);
    });
    console.log('[llm-test] /stream answer:', parts.join(''));
  } catch (err) {
    console.error('[llm-test] /stream error:', err);
  }
}
