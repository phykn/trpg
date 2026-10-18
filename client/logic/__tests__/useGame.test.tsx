// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { ko as copy } from '@/locale/ko';
import { ApiError, act, getCatalog, loadGame, startGame, streamNarration } from '@/services/api';
import { loadGameId, storeGameId } from '@/services/storage';
import type { GameView, NarrationEvent } from '@/services/types';
import { useGame } from '../useGame';

jest.mock('@/services/api', () => ({
  ApiError: class extends Error {
    status: number;
    constructor(code: number, message: string) { super(message); this.status = code; }
  },
  act: jest.fn(), getCatalog: jest.fn(), loadGame: jest.fn(), startGame: jest.fn(), streamNarration: jest.fn(),
}));
jest.mock('@/services/storage', () => ({ loadGameId: jest.fn(), storeGameId: jest.fn() }));

const meter = { id: 'd', name: 'Danger', value: 0, boxes: 6, fits: [] };
const saved: GameView = {
  game_id: 'g_saved', revision: 0, turn: 0, title: 'T', chapter: 'C', intro: 'intro',
  place: { id: 'square', name: 'Square', text: '' }, senses: [], exits: [], people: [], obstacles: [], danger: meter, tags: [],
  player: { approaches: [], traits: [], wounds: 0, gold: 0, items: [], knowledge: [], skills: [] },
  quests: [], buttons: [{ id: 'move:base', label: 'Go', enabled: true }],
  journal: [{ n: 0, input: '', lines: [], narration: 'opening' }], pending: null, ending: null, narrated: true,
};
const after: GameView = { ...saved, revision: 1, turn: 1, narrated: false, journal: [...saved.journal, { n: 1, input: 'Go', lines: [], narration: null }] };

type Game = ReturnType<typeof useGame>;
let current: Game;
let tree: ReturnType<typeof renderer.create>;
function Harness() { current = useGame(); return null; }
async function mount() { await flush(async () => { tree = renderer.create(<Harness />); }); }

function streams(...events: NarrationEvent[]) {
  (streamNarration as jest.Mock).mockImplementation(async (_id: string, _n: number, on: (e: NarrationEvent) => void) => {
    events.forEach(on);
  });
}

beforeEach(() => {
  jest.resetAllMocks();
  (getCatalog as jest.Mock).mockResolvedValue([{ id: 'harbor', title: 'Harbor', synopsis: '', creation: { choose: false, approaches: [], traits: [] } }]);
  (loadGameId as jest.Mock).mockReturnValue(saved.game_id);
  (storeGameId as jest.Mock).mockReturnValue(true);
  (loadGame as jest.Mock).mockResolvedValue(saved);
  (act as jest.Mock).mockResolvedValue({ kind: 'turn', view: after, turn: 1, options: [], reason: '' });
  streams({ type: 'delta', text: 'Wind' }, { type: 'done', text: 'Wind.', tags: {} });
});
afterEach(async () => { await flush(async () => { tree?.unmount(); }); });

test('restores the server snapshot using only the stored pointer', async () => {
  await mount();
  expect(current.view).toEqual(saved);
  expect(loadGame).toHaveBeenCalledWith(saved.game_id);
  expect(streamNarration).not.toHaveBeenCalled();
});

test('a restored turn without narration asks for it again', async () => {
  (loadGame as jest.Mock).mockResolvedValue(after);
  await mount();
  expect(streamNarration).toHaveBeenCalledWith(after.game_id, 1, expect.any(Function));
  expect(current.narration).toMatchObject({ status: 'done', text: 'Wind.' });
  expect(current.view?.journal[1].narration).toBe('Wind.');
});

test('a turn saves first and then streams its narration', async () => {
  await mount();
  await flush(async () => { await current.send({ text: 'Go' }); });
  expect(act).toHaveBeenCalledWith(saved.game_id, expect.objectContaining({ text: 'Go', revision: 0 }));
  expect(current.view?.revision).toBe(1);
  expect(streamNarration).toHaveBeenCalledWith(saved.game_id, 1, expect.any(Function));
  expect(current.narration.status).toBe('done');
});

test('a failed check resets the shown text before the rewrite', async () => {
  streams({ type: 'delta', text: 'Wrong' }, { type: 'reset' }, { type: 'delta', text: 'Right' }, { type: 'error', retry: true });
  await mount();
  await flush(async () => { await current.send({ action_id: 'move:base' }); });
  expect(current.narration).toMatchObject({ status: 'error', text: 'Right', canRetry: true });
});

test('clarify keeps the snapshot and offers the options', async () => {
  (act as jest.Mock).mockResolvedValue({ kind: 'clarify', view: saved, turn: null, options: [{ id: 'talk:a', label: 'A', enabled: true }], reason: '' });
  await mount();
  await flush(async () => { await current.send({ text: 'talk' }); });
  expect(current.notice).toEqual({ reason: copy.clarify, options: [{ id: 'talk:a', label: 'A', enabled: true }] });
  expect(streamNarration).not.toHaveBeenCalled();
});

test('double send fires one command before React renders busy state', async () => {
  await mount();
  await flush(async () => { await Promise.all([current.send({ text: 'Go' }), current.send({ text: 'Go' })]); });
  expect(act).toHaveBeenCalledTimes(1);
});

test('lost response freezes commands and retry reuses the exact receipt', async () => {
  (act as jest.Mock).mockRejectedValueOnce(new TypeError('Failed to fetch'));
  await mount();
  await flush(async () => { await current.send({ text: 'Go' }); });
  const original = (act as jest.Mock).mock.calls[0];
  expect(current.needsSync).toBe(true);
  expect(current.error).toBe(copy.connectionLost);
  await flush(async () => { await current.send({ text: 'Other' }); });
  expect(act).toHaveBeenCalledTimes(1);
  await flush(async () => { await current.retry(); });
  expect((act as jest.Mock).mock.calls[1]).toEqual(original);
  expect(current.needsSync).toBe(false);
});

test('stale commands reload the newer server snapshot', async () => {
  await mount();
  (act as jest.Mock).mockRejectedValueOnce(new ApiError(409, 'stale'));
  (loadGame as jest.Mock).mockResolvedValueOnce({ ...saved, revision: 3 });
  await flush(async () => { await current.send({ text: 'Go' }); });
  expect(current.view?.revision).toBe(3);
  await flush(async () => { await current.send({ text: 'Go' }); });
  expect((act as jest.Mock).mock.calls[1][1].revision).toBe(3);
});

test('new game stores its pointer and narrates the opening', async () => {
  (loadGameId as jest.Mock).mockReturnValue(null);
  (startGame as jest.Mock).mockResolvedValue({ ...saved, narrated: false });
  await mount();
  expect(current.creating).toBe(true);
  await flush(async () => { await current.start('harbor'); });
  expect(storeGameId).toHaveBeenCalledWith(saved.game_id);
  expect(streamNarration).toHaveBeenCalledWith(saved.game_id, 0, expect.any(Function));
});

test('failed restore keeps the pointer and still permits starting anew', async () => {
  (loadGame as jest.Mock).mockRejectedValue(new TypeError('Failed to fetch'));
  await mount();
  expect(current.error).toBe(copy.restoreFailed);
  expect(storeGameId).not.toHaveBeenCalled();
  await flush(async () => { current.openNew(); });
  expect(current.creating).toBe(true);
});
