import { clearGameId, loadGameId, storeGameId } from '../storage';

const original = Object.getOwnPropertyDescriptor(window, 'localStorage');
const useStorage = (storage: object) =>
  Object.defineProperty(window, 'localStorage', { configurable: true, ...storage });
afterEach(() => {
  if (original) Object.defineProperty(window, 'localStorage', original);
});

test('the game pointer is kept under the same key as before', () => {
  const items = new Map<string, string>();
  useStorage({ value: {
    getItem: (k: string) => items.get(k) ?? null,
    setItem: (k: string, v: string) => { items.set(k, v); },
    removeItem: (k: string) => { items.delete(k); },
  } });
  expect(loadGameId()).toBeNull();
  storeGameId('g1');
  expect([...items]).toEqual([['trpg.game_id', 'g1']]);
  expect(loadGameId()).toBe('g1');
  clearGameId();
  expect(loadGameId()).toBeNull();
});

test('storage that refuses access or is full does not stop the game', () => {
  useStorage({ get() { throw new Error('denied'); } });
  expect(loadGameId()).toBeNull();
  expect(() => { storeGameId('g1'); clearGameId(); }).not.toThrow();
  useStorage({ value: { setItem() { throw new Error('quota exceeded'); } } });
  expect(() => storeGameId('g1')).not.toThrow();
});
