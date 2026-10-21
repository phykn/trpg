// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { ko } from '@/locale/ko';
import { ApiError, getGame, getStories, sendCommand, stream } from '@/services/api';
import { clearGameId, loadGameId } from '@/services/storage';
import type { CommandResult, GameView, NarrationEvent, StepRecord } from '@/services/types';
import { destination, useGame } from '../useGame';

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
  revision: 0, story: { id: 's', title: 'S', premise: 'P' }, chapter: { k: 1, title: 'C', aim: 'A' },
  scene: { place: { id: 'dock', name: 'Dock', senses: ['wind'] }, people: [], things: [], obstacles: [], exits: [], tags: [] },
  player: { name: "N", approaches: [], traits: [], tags: [], things: [], wounds: 0, wound_boxes: 2, beats: 0, beats_max: 6, growth: 0 },
  clocks: [], journal: { beliefs: [], owes: [], relations: [], choices: [] },
  buttons: [{ action: 'go:village', label: 'Go', rolls: false }], growth: [], card: null, last: null,
  recaps: [], ending: null,
};
const walk: StepRecord = {
  t: 0, action: 'go:village', label: 'Go', result: 'none', risk: 'low', dc: null, roll: null, mods: [], total: null, decisive: [], changes: [],
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
  // A step with nothing to animate ends its reveal on a 0 ms timer, which real timers may fire mid-flush.
  jest.useFakeTimers();
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
  expect(game.narration.error).toBe('down');
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

test('commands stay locked while the turn is revealed and narrated', async () => {
  (sendCommand as jest.Mock).mockResolvedValue(turn(after()));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.phase).toBe('revealing');
  await run(() => game.command({ text: 'run' }));
  await run(() => game.skip());
  expect(game.phase).toBe('narrating');
  await run(() => game.command({ text: 'run' }));
  expect(sendCommand).toHaveBeenCalledTimes(1);
  await run(() => game.typed());
  await run(() => game.command({ text: 'run' }));
  expect(sendCommand).toHaveBeenCalledTimes(2);
});

test('a network error is stuck at once, and only the identical command may follow', async () => {
  (sendCommand as jest.Mock).mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce(turn(after()));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.phase).toBe('stuck');
  await run(() => game.command({ action: 'go:dock' }));
  expect(sendCommand).toHaveBeenCalledTimes(1);
  await run(() => game.resend());
  const [first, second] = (sendCommand as jest.Mock).mock.calls;
  expect(second).toEqual(first);
  expect(game.phase).toBe('revealing');
});

test('a late copy of a lost answer, after the resend was answered, changes nothing', async () => {
  let answer: (r: CommandResult) => void = () => undefined;
  let lose: (e: unknown) => void = () => undefined;
  (sendCommand as jest.Mock)
    .mockReturnValueOnce(new Promise((ok) => { answer = ok; }))
    .mockResolvedValueOnce(turn(after()))
    .mockReturnValueOnce(new Promise((_, no) => { lose = no; }))
    .mockResolvedValueOnce(turn(after({ revision: 2 })));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => jest.advanceTimersByTime(30_000));
  await run(() => game.resend());
  await run(() => game.skip());
  await run(() => game.typed());
  expect(game.phase).toBe('idle');
  await run(() => answer(turn(after())));
  expect(game.phase).toBe('idle');
  expect(stream).toHaveBeenCalledTimes(1);
  // The same for a lost request that fails after its resend was answered.
  await run(() => game.command({ action: 'go:village' }));
  await run(() => jest.advanceTimersByTime(30_000));
  await run(() => game.resend());
  await run(() => game.skip());
  await run(() => game.typed());
  await run(() => lose(new TypeError('network')));
  expect(game.phase).toBe('idle');
  expect(game.view?.revision).toBe(2);
});

test('growth opens after the turn is told; later puts it aside until reopened', async () => {
  const growth: GameView['growth'] = [{ action: 'grow:force', label: 'Force', kind: 'approach', name: 'force 1→2' }];
  (sendCommand as jest.Mock).mockResolvedValue(turn(after({ growth })));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  expect(game.phase).toBe('narrating');
  await run(() => game.typed());
  expect(game.phase).toBe('card');
  await run(() => game.laterGrowth());
  expect(game.phase).toBe('idle');
  expect(game.growthLater).toBe(true);
  await run(() => game.openGrowth());
  expect(game.phase).toBe('card');
});

test('tag names from the narration rename the hero and scene tags', async () => {
  const tagged = after({
    player: { ...base.player, tags: [{ slot: 1, kind: 'snag', life: 'scene', name: 'snag' }] },
    scene: { ...base.scene, tags: [{ owner: 'dock', slot: 2, kind: 'edge', life: 'scene', name: 'edge' }] },
  });
  (sendCommand as jest.Mock).mockResolvedValue(turn(tagged));
  narrates({ type: 'text', text: 'Spray.' }, { type: 'done', tags: [
    { slot: 1, owner: 'player', name: 'Wet feet' }, { slot: 2, owner: 'dock', name: 'Tide' },
  ] });
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.view?.player.tags[0].name).toBe('Wet feet');
  expect(game.view?.scene.tags[0].name).toBe('Tide');
});

test('rows keep the previous view until the reveal ends', async () => {
  (sendCommand as jest.Mock).mockResolvedValue(turn(after()));
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  expect(game.view?.revision).toBe(1);
  expect(game.before?.revision).toBe(0);
  await run(() => game.skip());
  expect(game.before).toBeNull();
});

test('reopening a game narrates its last turn before commands open', async () => {
  (getGame as jest.Mock).mockResolvedValue(after());
  await mount();
  expect(stream).toHaveBeenCalledWith('/n/g_1/1', expect.any(Function));
  expect(game.phase).toBe('narrating');
  expect(game.narration.text).toBe('Wind.');
  expect(game.reveal).toBeNull();
  await run(() => game.typed());
  expect(game.phase).toBe('idle');
});

test('a failed chapter recap is a narration error, and retrying fetches both again', async () => {
  const chapter: StepRecord = { ...walk, changes: [{ kind: 'chapter', from: 1, to: 2 }] };
  (sendCommand as jest.Mock).mockResolvedValue(turn(after({ chapter: { k: 2, title: 'C2', aim: 'B' } }), [chapter]));
  let recap: NarrationEvent[] = [{ type: 'error' }];
  (stream as jest.Mock).mockImplementation(async (path: string, on: (e: NarrationEvent) => void) => {
    (path.startsWith('/r/') ? recap : [{ type: 'text', text: 'Wind.' }, { type: 'done', tags: [] }] as NarrationEvent[]).forEach(on);
  });
  await mount();
  await run(() => game.command({ action: 'go:village' }));
  await run(() => game.skip());
  expect(stream).toHaveBeenCalledWith('/r/g_1/1', expect.any(Function));
  expect(game.phase).toBe('narration_error');
  recap = [{ type: 'text', text: 'So far.' }, { type: 'done', tags: [] }];
  await run(() => game.retryNarration());
  expect(game.narration).toMatchObject({ text: 'Wind.', recap: 'So far.' });
  await run(() => game.typed());
  expect(game.phase).toBe('idle');
});

test('the destination follows ending, card, growth, then idle', () => {
  const growth: GameView['growth'] = [{ action: 'grow:force', label: 'Force', kind: 'approach', name: 'force 1→2' }];
  expect(destination({ ...base, growth, card: rollCard, ending: { id: 'e', title: 'E' } }, false)).toBe('ending');
  expect(destination({ ...base, growth, card: rollCard }, true)).toBe('card');
  expect(destination({ ...base, growth }, false)).toBe('card');
  expect(destination({ ...base, growth }, true)).toBe('idle');
  expect(destination(base, false)).toBe('idle');
});
