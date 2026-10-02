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

test('sends authenticated structured choices without changing the receipt', async () => {
  const view = { game_id: 'adv_saved', revision: 1 };
  (fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => view });
  const command = { option_id: 'move:tavern', revision: 0, request_id: 'same-receipt' };
  expect(await api.chooseOption('adv_saved', command)).toEqual(view);
  expect(fetch).toHaveBeenCalledWith('http://localhost:8000/adventure/adv_saved/choose', expect.objectContaining({
    method: 'POST', body: JSON.stringify(command),
    headers: { Authorization: `Basic ${btoa('local:local')}`, 'Content-Type': 'application/json' },
  }));
  expect(jest.getTimerCount()).toBe(0);
});

test('keeps a server conflict message and status for recovery', async () => {
  (fetch as jest.Mock).mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: 'stale choice' }) });
  await expect(api.loadGame('adv_saved')).rejects.toMatchObject({ status: 409, message: 'stale choice' });
  expect(jest.getTimerCount()).toBe(0);
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

test('timeout also covers a response body that stops arriving', async () => {
  (fetch as jest.Mock).mockImplementation(async (_url, init) => ({
    ok: true,
    json: () => new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new Error('body aborted')));
    }),
  }));
  const result = expect(api.getCatalog()).rejects.toThrow('body aborted');
  await jest.advanceTimersByTimeAsync(15_000);
  await result;
});
