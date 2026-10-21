import { clearGameId, loadGameId, loadLog, storeGameId, storeLog } from '../storage';

const descriptor = Object.getOwnPropertyDescriptor(window, 'localStorage');
const storage = { getItem: jest.fn(), setItem: jest.fn() };
beforeEach(() => {
  jest.resetAllMocks();
  Object.defineProperty(window, 'localStorage', { configurable: true, value: storage });
});
afterAll(() => {
  if (descriptor) Object.defineProperty(window, 'localStorage', descriptor);
  else Reflect.deleteProperty(window, 'localStorage');
});

test('continues to use the existing browser pointer', () => {
  storage.getItem.mockReturnValue('g_saved');
  expect(loadGameId()).toBe('g_saved');
  expect(storage.getItem).toHaveBeenCalledWith('trpg.game_id');
  expect(storeGameId('g_next')).toBe(true);
  expect(storage.setItem).toHaveBeenCalledWith('trpg.game_id', 'g_next');
});

test('denied storage access does not crash the game', () => {
  Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new Error('denied'); } });
  expect(loadGameId()).toBeNull();
  expect(storeGameId('g_next')).toBe(false);
});

test('a full storage device reports that the pointer could not be saved', () => {
  storage.setItem.mockImplementation(() => { throw new Error('quota exceeded'); });
  expect(storeGameId('g_next')).toBe(false);
});

// A device's storage as the browser keeps it, so what one call writes the next can read.
function device(seed: Record<string, string> = {}) {
  const items = new Map(Object.entries(seed));
  const store = {
    get length() { return items.size; },
    key: (i: number) => [...items.keys()][i] ?? null,
    getItem: (k: string) => items.get(k) ?? null,
    setItem: (k: string, v: string) => { items.set(k, v); },
    removeItem: (k: string) => { items.delete(k); },
  };
  Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
  return items;
}

test('a 404 clears the pointer, so the next start does not reopen a deleted game', () => {
  const items = device({ 'trpg.game_id': 'g_gone' });
  clearGameId();
  expect(items.has('trpg.game_id')).toBe(false);
  expect(loadGameId()).toBeNull();
});

test('the chat history survives a reload, and only the saved game keeps one', () => {
  const items = device({ 'trpg.log.g_old': '[]', 'trpg.game_id': 'g_new' });
  storeLog('g_new', [{ id: 'you:1', kind: 'you', text: 'a' }]);
  expect(loadLog('g_new')).toEqual([{ id: 'you:1', kind: 'you', text: 'a' }]);
  expect([...items.keys()].sort()).toEqual(['trpg.game_id', 'trpg.log.g_new']);
});
