// The command lifecycle over the real api module, with only the network replaced: what goes on the wire and what
// the client makes of each answer.
// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { fetch } from 'expo/fetch';
import { ko } from '@/locale/ko';
import type { GameView, StepRecord } from '@/services/types';

jest.mock('expo/fetch', () => ({ fetch: jest.fn() }));
jest.mock('@/services/storage', () => ({ loadGameId: jest.fn(() => 'g_1'), storeGameId: jest.fn(() => true), clearGameId: jest.fn() }));
process.env.EXPO_PUBLIC_API_URL = 'http://t';
process.env.EXPO_PUBLIC_API_USER = 'u';
process.env.EXPO_PUBLIC_API_PASS = 'p';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const { useGame } = require('../useGame') as typeof import('../useGame');

const base: GameView = {
  revision: 0, story: { id: 's', title: 'S', premise: 'P' }, chapter: { k: 1, title: 'C', aim: 'A' },
  scene: { place: { id: 'dock', name: 'Dock', senses: [] }, people: [], things: [], obstacles: [], exits: [], tags: [] },
  player: { name: 'N', approaches: [], traits: [], tags: [], things: [], wounds: 0, wound_boxes: 2, beats: 0, beats_max: 6, growth: 0 },
  clocks: [], journal: { beliefs: [], owes: [], relations: [], choices: [] },
  buttons: [], growth: [], card: null, last: null, recaps: [], ending: null,
};
const walk: StepRecord = {
  t: 0, action: 'go:village', label: 'Go', result: 'none', risk: 'low', dc: null, roll: null, mods: [], total: null, decisive: [], changes: [],
};
const moved = (revision: number): GameView => ({ ...base, revision, last: { turn: revision, steps: [walk], narrated: false } });

type Reply = { status?: number; json?: unknown; lines?: string[] };
function reply({ status = 200, json, lines }: Reply) {
  const chunks = (lines ?? []).map((l) => new TextEncoder().encode(l));
  return {
    ok: status >= 200 && status < 300, status,
    json: async () => { if (json === undefined) throw new SyntaxError('not JSON'); return json; },
    body: lines ? { getReader: () => ({ read: async () => (chunks.length ? { done: false, value: chunks.shift() } : { done: true, value: undefined }) }) } : null,
  };
}

let commands: Reply[];
let narration: Reply;
const sent = () => (fetch as jest.Mock).mock.calls.filter(([url]) => url.endsWith('/commands'));

let game: ReturnType<typeof useGame>;
let tree: { unmount: () => void } | undefined;
function Harness() { game = useGame(); return null; }
async function run(fn: () => unknown) { await flush(async () => { await fn(); }); }

beforeEach(() => {
  jest.useFakeTimers();
  commands = [];
  narration = { lines: ['{"type":"text","text":"Wind."}\n', '{"type":"done","tags":[]}\n'] };
  (fetch as jest.Mock).mockReset().mockImplementation(async (url: string) => {
    if (url === 'http://t/stories') return reply({ json: [] });
    if (url === 'http://t/games/g_1') return reply({ json: base });
    if (url === 'http://t/games/g_1/commands') return reply(commands.shift() as Reply);
    if (url.startsWith('http://t/games/g_1/turns/')) return reply(narration);
    throw new Error(`unexpected ${url}`);
  });
});
afterEach(async () => { await flush(async () => { tree?.unmount(); }); jest.useRealTimers(); });

async function mount() { await flush(async () => { tree = renderer.create(<Harness />); }); }

test('each command posts its request id, the adopted revision and its body, with Basic Auth', async () => {
  commands = [{ json: { kind: 'turn', turn: 1, steps: [walk], reason: null, view: moved(1) } },
    { json: { kind: 'turn', turn: 2, steps: [walk], reason: null, view: moved(2) } }];
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  await run(() => game.typed());
  expect(game.phase).toBe('idle');
  await run(() => game.command({ text: 'look around' }));
  const [[, first], [, second]] = sent();
  expect(first).toMatchObject({ method: 'POST', headers: { Authorization: `Basic ${btoa('u:p')}` } });
  const a = JSON.parse(first.body);
  const b = JSON.parse(second.body);
  expect(a).toEqual({ request_id: expect.any(String), revision: 0, action: 'go:village' });
  expect(b).toEqual({ request_id: expect.any(String), revision: 1, text: 'look around' });
  expect(b.request_id).not.toBe(a.request_id);
});

test('a 409 carrying a view is adopted, and the next command sends its revision', async () => {
  commands = [{ status: 409, json: { view: { ...base, revision: 7 } } },
    { json: { kind: 'turn', turn: 8, steps: [walk], reason: null, view: moved(8) } }];
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.phase).toBe('idle');
  expect(game.notice).toBe(ko.conflict);
  expect(game.view?.revision).toBe(7);
  await run(() => game.command({ action: 'go:village' }));
  expect(JSON.parse(sent()[1][1].body).revision).toBe(7);
});

test('a 422 shows the server reason and leaves the view', async () => {
  commands = [{ status: 422, json: { reason: '이해하지 못했습니다.' } }];
  await mount();
  await run(() => game.command({ text: '?' }));
  expect(game.phase).toBe('idle');
  expect(game.notice).toBe('이해하지 못했습니다.');
});

test('a server error with no JSON body shows a fixed notice and leaves the view', async () => {
  commands = [{ status: 500 }];
  await mount();
  await run(() => game.command({ text: '문을 연다' }));
  expect(game.phase).toBe('idle');
  expect(game.notice).toBe(ko.serverError);
  expect(game.view?.revision).toBe(0);
});

test('a narration stream that ends before done is a narration error', async () => {
  commands = [{ json: { kind: 'turn', turn: 1, steps: [walk], reason: null, view: moved(1) } }];
  narration = { lines: ['{"type":"text","text":"Wind."}\n'] };
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  expect(game.phase).toBe('narration_error');
  expect(game.narration.error).toBe('');
});

test('a narration answered with an error status is a narration error', async () => {
  commands = [{ json: { kind: 'turn', turn: 1, steps: [walk], reason: null, view: moved(1) } }];
  narration = { status: 503 };
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  expect(game.phase).toBe('narration_error');
});
