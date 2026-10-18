import { fetch } from 'expo/fetch';
import { ko } from '@/locale/ko';

jest.mock('expo/fetch', () => ({ fetch: jest.fn() }));
let api: typeof import('../api');

beforeAll(() => {
  process.env.EXPO_PUBLIC_API_URL = 'http://localhost:8000';
  process.env.EXPO_PUBLIC_API_USER = 'local';
  process.env.EXPO_PUBLIC_API_PASS = 'local';
  api = require('../api');
});
beforeEach(() => {
  jest.resetAllMocks();
  jest.useFakeTimers();
});
afterEach(() => jest.useRealTimers());

const headers = { Authorization: `Basic ${btoa('local:local')}`, 'Content-Type': 'application/json' };

test('sends an authenticated act envelope without changing the receipt', async () => {
  const result = { kind: 'turn', turn: 1 };
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => result });
  const envelope = { text: '문을 연다', revision: 0, request_id: 'same-receipt' };
  expect(await api.act('g_saved', envelope)).toEqual(result);
  expect(fetch).toHaveBeenCalledWith('http://localhost:8000/games/g_saved/act', expect.objectContaining({
    method: 'POST', body: JSON.stringify(envelope), headers,
  }));
  expect(jest.getTimerCount()).toBe(0);
});

test('starts a story with or without creation choices', async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => ({}) });
  await api.startGame('harbor');
  await api.startGame('harbor', { approaches: { wits: 2 }, traits: ['a', 'b'] });
  expect((fetch as jest.Mock).mock.calls[0][1].body).toBe(JSON.stringify({ story: 'harbor' }));
  expect((fetch as jest.Mock).mock.calls[1][1].body).toBe(JSON.stringify({ story: 'harbor', approaches: { wits: 2 }, traits: ['a', 'b'] }));
});

test('keeps a server conflict message and status for recovery', async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: 'stale' }) });
  await expect(api.loadGame('g_saved')).rejects.toMatchObject({ status: 409, message: 'stale' });
});

test.each([
  [401, async () => ({ detail: 'Not authenticated' })],
  [502, async () => { throw new Error('HTML response'); }],
  [422, async () => ({ detail: [{ type: 'missing' }] })],
])('uses a readable fallback for HTTP %s', async (status, json) => {
  (fetch as jest.Mock).mockResolvedValue({ ok: false, status, json });
  await expect(api.getCatalog()).rejects.toMatchObject({ status, message: ko.requestFailed });
});

test('aborts a stalled request after fifteen seconds', async () => {
  (fetch as jest.Mock).mockImplementation((_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const result = expect(api.getCatalog()).rejects.toThrow('aborted');
  await jest.advanceTimersByTimeAsync(15_000);
  await result;
  expect(jest.getTimerCount()).toBe(0);
});

test('reads narration events split across chunks', async () => {
  const encoder = new TextEncoder();
  const chunks = ['{"type":"delta","text":"안"}\n{"type":"del', 'ta","text":"녕"}\n', '{"type":"done","text":"안녕","tags":{}}\n'];
  const reader = { read: jest.fn() };
  chunks.forEach((c) => reader.read.mockResolvedValueOnce({ done: false, value: encoder.encode(c) }));
  reader.read.mockResolvedValueOnce({ done: true, value: undefined });
  (fetch as jest.Mock).mockResolvedValue({ ok: true, body: { getReader: () => reader } });
  const events: unknown[] = [];
  await api.streamNarration('g_saved', 3, (e) => events.push(e));
  expect(fetch).toHaveBeenCalledWith('http://localhost:8000/games/g_saved/turns/3/narration', expect.objectContaining({ headers }));
  expect(events).toEqual([
    { type: 'delta', text: '안' }, { type: 'delta', text: '녕' }, { type: 'done', text: '안녕', tags: {} },
  ]);
  expect(jest.getTimerCount()).toBe(0);
});
