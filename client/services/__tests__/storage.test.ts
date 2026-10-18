import { loadGameId, storeGameId } from '../storage';

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
