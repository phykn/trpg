// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act } from 'react-test-renderer';

import { ko as copy } from '@/locale/ko';
import { ApiError, chooseOption, getCatalog, loadGame, startGame } from '@/services/api';
import { loadGameId, storeGameId } from '@/services/storage';
import type { GameView } from '@/services/types';
import { useGame } from '../useGame';

jest.mock('@/services/api', () => ({
  ApiError: class extends Error {
    status: number;
    constructor(code: number, message: string) { super(message); this.status = code; }
  },
  chooseOption: jest.fn(), getCatalog: jest.fn(), loadGame: jest.fn(), startGame: jest.fn(),
}));
jest.mock('@/services/storage', () => ({ loadGameId: jest.fn(), storeGameId: jest.fn() }));

const saved: GameView = {
  game_id: 'adv_saved', revision: 0, title: 'Harbor', player_name: 'Tester', role: 'Listener',
  hp: 8, max_hp: 8, mp: 4, max_mp: 4, gold: 12,
  scene: { id: 'square', name: 'Square', text: '' }, characters: [], objective: '', clock: '', alert: '', remaining: 24,
  actions: [], knowledge: [], inventory: [], skills: [], journal: [], combat: null, ending: null,
};
const after = { ...saved, revision: 1, remaining: 23 };

type Game = ReturnType<typeof useGame>;
let current: Game;
let tree: ReturnType<typeof renderer.create>;
function Harness() { current = useGame(); return null; }
async function mount() { await act(async () => { tree = renderer.create(<Harness />); }); }

beforeEach(() => {
  jest.resetAllMocks();
  (getCatalog as jest.Mock).mockResolvedValue({ title: 'Harbor', synopsis: '', roles: [{ id: 'listener', name: 'Listener', text: '' }] });
  (loadGameId as jest.Mock).mockReturnValue(saved.game_id);
  (storeGameId as jest.Mock).mockReturnValue(true);
  (loadGame as jest.Mock).mockResolvedValue(saved);
  (chooseOption as jest.Mock).mockResolvedValue(after);
});
afterEach(async () => { await act(async () => { tree?.unmount(); }); });

test('restores the authoritative server snapshot using only the stored pointer', async () => {
  await mount();
  expect(current.view).toEqual(saved);
  expect(loadGame).toHaveBeenCalledWith(saved.game_id);
  expect(current.busy).toBe(false);
  expect(current.creating).toBe(false);
});

test('new game records its pointer after server creation succeeds', async () => {
  (loadGameId as jest.Mock).mockReturnValue(null);
  (startGame as jest.Mock).mockResolvedValue(saved);
  await mount();
  expect(current.creating).toBe(true);
  await act(async () => { await current.start('Tester', 'listener'); });
  expect(current.view).toEqual(saved);
  expect(current.creating).toBe(false);
  expect(storeGameId).toHaveBeenCalledWith(saved.game_id);
});

test('double click sends only one command even before React renders busy state', async () => {
  await mount();
  await act(async () => { await Promise.all([current.choose('move:tavern'), current.choose('move:tavern')]); });
  expect(chooseOption).toHaveBeenCalledTimes(1);
  expect(current.view?.revision).toBe(1);
});

test('lost response freezes choices and retry reuses the exact command receipt', async () => {
  (chooseOption as jest.Mock).mockRejectedValueOnce(new TypeError('Failed to fetch'));
  await mount();
  await act(async () => { await current.choose('move:tavern'); });
  const original = (chooseOption as jest.Mock).mock.calls[0];
  expect(current.needsSync).toBe(true);
  expect(current.error).toBe(copy.connectionLost);
  expect(current.view).toEqual(saved);
  await act(async () => { await current.choose('move:warehouse'); });
  expect(chooseOption).toHaveBeenCalledTimes(1);
  await act(async () => { await current.retry(); });
  expect((chooseOption as jest.Mock).mock.calls[1]).toEqual(original);
  expect(current.needsSync).toBe(false);
  expect(current.view?.remaining).toBe(23);
});

test('stale choices reload the newer server scene before another choice', async () => {
  await mount();
  (chooseOption as jest.Mock).mockRejectedValueOnce(new ApiError(409, 'stale'));
  (loadGame as jest.Mock).mockResolvedValueOnce({ ...saved, revision: 3 });
  await act(async () => { await current.choose('move:tavern'); });
  expect(current.view?.revision).toBe(3);
  expect(current.needsSync).toBe(false);
  await act(async () => { await current.choose('move:warehouse'); });
  expect((chooseOption as jest.Mock).mock.calls[1][1].revision).toBe(3);
});

test('failed restore preserves the pointer and still permits starting anew', async () => {
  (loadGame as jest.Mock).mockRejectedValue(new TypeError('Failed to fetch'));
  await mount();
  expect(current.error).toBe(copy.restoreFailed);
  expect(storeGameId).not.toHaveBeenCalled();
  await act(async () => { current.openNew(); });
  expect(current.creating).toBe(true);
  expect(current.catalog).not.toBeNull();
});

test('unavailable browser storage does not discard a successfully saved turn', async () => {
  (storeGameId as jest.Mock).mockReturnValue(false);
  await mount();
  await act(async () => { await current.choose('move:tavern'); });
  expect(current.view).toEqual(after);
  expect(current.error).toBe(copy.storageUnavailable);
  expect(current.needsSync).toBe(false);
});

test('visiting the new-game form cannot hide recovery for an uncertain command', async () => {
  (chooseOption as jest.Mock).mockRejectedValueOnce(new TypeError('Failed to fetch'));
  await mount();
  await act(async () => { await current.choose('move:tavern'); });
  await act(async () => { current.openNew(); });
  await act(async () => { current.resume(); });
  expect(current.needsSync).toBe(true);
  expect(current.error).toBe(copy.connectionLost);
  await act(async () => { await current.retry(); });
  expect(current.needsSync).toBe(false);
  expect(current.view).toEqual(after);
});
