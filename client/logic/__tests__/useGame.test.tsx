// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { ko } from '@/locale/ko';
import { ApiError, getGame, getStories, sendCommand, stream } from '@/services/api';
import { clearGameId, loadGameId } from '@/services/storage';
import type { CommandResult, GameView, NarrationEvent, StepRecord } from '@/services/types';
import { useGame } from '../useGame';

jest.mock('@/services/api', () => ({
  ApiError: class extends Error {
    status: number; view: unknown; reason: unknown;
    constructor(status: number, view: unknown, reason: unknown) { super('x'); this.status = status; this.view = view; this.reason = reason; }
  },
  getStories: jest.fn(), getGame: jest.fn(), sendCommand: jest.fn(), createGame: jest.fn(), stream: jest.fn(),
  narrationPath: (id: string, n: number) => `/n/${id}/${n}`, recapPath: (id: string, k: number) => `/r/${id}/${k}`,
}));
jest.mock('@/services/storage', () => ({ loadGameId: jest.fn(), storeGameId: jest.fn(() => true), clearGameId: jest.fn() }));

const base: GameView = {
  revision: 0, chapter: { k: 1, title: 'C' },
  scene: { place: { id: 'dock', name: 'Dock', senses: ['wind'] }, people: [], things: [], obstacles: [], exits: [], tags: [] },
  player: { approaches: [], traits: [], tags: [], things: [], wounds: 0, wound_boxes: 2, beats: 0, beats_max: 6, growth: 0 },
  clocks: [], journal: { beliefs: [], owes: [], relations: [], choices: [] },
  buttons: [{ action: 'go:village', label: 'Go', rolls: false }], due: [], growth: [], card: null, last: null,
  recaps: [], bands: { mixed: 7, success: 10, min: 1, max: 16 }, ending: null,
};
const walk: StepRecord = {
  t: 0, action: 'go:village', label: 'Go', result: 'none', risk: 'low', roll: null, mods: [], total: null, decisive: [], changes: [],
};
const rollCard = {
  id: 'c1', kind: 'roll' as const, echo: { text: 'x', slots: [] }, selected: 'try:door:finesse',
  plan: { step: { action: 'try:door:finesse', label: 'Door', target: { id: 'door', name: 'Door', fill: 0, boxes: 3 } }, rest: [] },
  options: [{ id: 'try:door:finesse', label: 'none' }],
};
const after = (patch: Partial<GameView> = {}): GameView => ({ ...base, revision: 1, last: { turn: 1, steps: [walk], narrated: false }, ...patch });
const turn = (view: GameView, steps = [walk]): CommandResult => ({ kind: 'turn', turn: 1, steps, reason: null, view });

type G = ReturnType<typeof useGame>;
let game: G;
let tree: { unmount: () => void } | undefined;
function Harness() { game = useGame(); return null; }
async function mount() { await flush(async () => { tree = renderer.create(<Harness />); }); }
async function run(fn: () => unknown) { await flush(async () => { await fn(); }); }

function narrates(...events: NarrationEvent[]) {
  (stream as jest.Mock).mockImplementation(async (_p: string, on: (e: NarrationEvent) => void) => { events.forEach(on); });
}

beforeEach(() => {
  jest.resetAllMocks();
  (getStories as jest.Mock).mockResolvedValue([]);
  (loadGameId as jest.Mock).mockReturnValue('g_1');
  (getGame as jest.Mock).mockResolvedValue(base);
  narrates({ type: 'stage', stage: 'writing' }, { type: 'text', text: 'Wind.' }, { type: 'done', tags: [] });
});
afterEach(async () => { await flush(async () => { tree?.unmount(); }); jest.useRealTimers(); });

test('restoring keeps the pointer and lands on the view', async () => {
  await mount();
  expect(getGame).toHaveBeenCalledWith('g_1');
  expect(game.phase).toBe('idle');
  expect(clearGameId).not.toHaveBeenCalled();
});

test('a failed restore blocks without clearing the pointer; a missing game clears it', async () => {
  (getGame as jest.Mock).mockRejectedValueOnce(new TypeError('network'));
  await mount();
  expect(game.phase).toBe('blocked');
  expect(clearGameId).not.toHaveBeenCalled();
  await flush(async () => { tree?.unmount(); });
  (getGame as jest.Mock).mockRejectedValueOnce(new ApiError(404, null, null));
  await mount();
  expect(game.phase).toBe('start');
  expect(clearGameId).toHaveBeenCalled();
});

test('a step reveals, narrates, and returns to idle once typed', async () => {
  (sendCommand as jest.Mock).mockResolvedValue(turn(after()));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.phase).toBe('revealing');
  await run(() => game.skip());
  expect(game.phase).toBe('narrating');
  expect(game.narration.text).toBe('Wind.');
  await run(() => game.typed());
  expect(game.phase).toBe('idle');
  expect(game.view?.revision).toBe(1);
});

test('steps before a card are revealed and narrated before the card opens', async () => {
  (sendCommand as jest.Mock).mockResolvedValue({ ...turn(after({ card: rollCard })), kind: 'card' });
  await mount();
  await run(() => game.command({ text: 'go and open' }));
  await run(() => game.skip());
  await run(() => game.typed());
  expect(game.phase).toBe('card');
});

test('a card answer with no steps opens the card at once', async () => {
  (sendCommand as jest.Mock).mockResolvedValue({ kind: 'card', turn: null, steps: [], reason: null, view: { ...base, revision: 1, card: rollCard } });
  await mount();
  await run(() => game.command({ action: 'try:door:finesse' }));
  expect(game.phase).toBe('card');
});

test('releasing the dice rolls, and the reveal waits for the cloud', async () => {
  jest.useFakeTimers();
  (getGame as jest.Mock).mockResolvedValue({ ...base, card: rollCard });
  const rolled: StepRecord = { ...walk, action: 'try:door:finesse', result: 'success', roll: { d1: 5, d2: 5 }, total: 10 };
  (sendCommand as jest.Mock).mockResolvedValue(turn(after(), [rolled]));
  await mount();
  expect(game.phase).toBe('card');
  await run(() => game.command({ card: 'c1', pick: 'try:door:finesse' }));
  expect(game.phase).toBe('rolling');
  await run(() => jest.advanceTimersByTime(650));
  expect(game.phase).toBe('revealing');
  expect(game.reveal?.card?.id).toBe('c1');
});

test('a cost due opens the cost card', async () => {
  (sendCommand as jest.Mock).mockResolvedValue(turn(after({ due: [{ action: 'pay:engine.snag', name: 'snag', weight: 'light' }] })));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  await run(() => game.typed());
  expect(game.phase).toBe('card');
});

test('409 with a view adopts it; 409 incompatible blocks', async () => {
  const fresh = { ...base, revision: 5 };
  (sendCommand as jest.Mock).mockRejectedValueOnce(new ApiError(409, fresh, null));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.view?.revision).toBe(5);
  expect(game.notice).toBe(ko.conflict);
  expect(game.phase).toBe('idle');
  (sendCommand as jest.Mock).mockRejectedValueOnce(new ApiError(409, null, 'incompatible'));
  await run(() => game.command({ action: 'go:village' }));
  expect(game.phase).toBe('blocked');
});

test('a missing answer is stuck until the identical command is sent again', async () => {
  jest.useFakeTimers();
  (sendCommand as jest.Mock).mockReturnValueOnce(new Promise(() => undefined)).mockResolvedValueOnce(turn(after()));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => jest.advanceTimersByTime(30_000));
  expect(game.phase).toBe('stuck');
  await run(() => game.command({ action: 'go:dock' }));          // nothing else is accepted
  expect(sendCommand).toHaveBeenCalledTimes(1);
  await run(() => game.resend());
  const [first, second] = (sendCommand as jest.Mock).mock.calls;
  expect(second).toEqual(first);
  expect(game.phase).toBe('revealing');
});

test('a refusal shows its reason and leaves the view', async () => {
  (sendCommand as jest.Mock).mockResolvedValue({ kind: 'refused', turn: null, steps: [], reason: 'no', view: base });
  await mount();
  await run(() => game.command({ text: 'fly' }));
  expect(game.notice).toBe('no');
  expect(game.phase).toBe('idle');
});

test('a broken narration stream offers to fetch it again', async () => {
  (sendCommand as jest.Mock).mockResolvedValue(turn(after()));
  narrates({ type: 'error', message: 'down' });
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  expect(game.phase).toBe('narration_error');
  narrates({ type: 'text', text: 'Again.' }, { type: 'done', tags: [] });
  await run(() => game.retryNarration());
  expect(game.narration.text).toBe('Again.');
});

test('the ending keeps the recap narrated with its turn, which the view does not list yet', async () => {
  const end: StepRecord = { ...walk, changes: [{ kind: 'ending', id: 'wreck' }] };
  (sendCommand as jest.Mock).mockResolvedValue(turn(after({ ending: { id: 'wreck', title: 'W' }, recaps: [] }), [end]));
  narrates({ type: 'text', text: 'Last.' }, { type: 'done', tags: [] });
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  await run(() => game.typed());
  expect(game.phase).toBe('ending');
  expect(stream).toHaveBeenCalledWith('/r/g_1/1', expect.any(Function));
  expect(game.recaps[1]).toBe('Last.');
});

test('the menu goes to the start screen, which resumes the same game', async () => {
  await mount();
  await run(() => game.toTitle());
  expect(game.phase).toBe('start');
  expect(game.canResume).toBe(true);
  expect(clearGameId).not.toHaveBeenCalled();
  await run(() => game.resume());
  expect(game.phase).toBe('idle');
  expect(getGame).toHaveBeenCalledTimes(1);
});
