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
  storage.getItem.mockReturnValue('adv_saved');
  expect(loadGameId()).toBe('adv_saved');
  expect(storage.getItem).toHaveBeenCalledWith('trpg.adventure_game_id');
  expect(storeGameId('adv_next')).toBe(true);
  expect(storage.setItem).toHaveBeenCalledWith('trpg.adventure_game_id', 'adv_next');
});

test('denied storage access does not crash the game', () => {
  Object.defineProperty(window, 'localStorage', { configurable: true, get() { throw new Error('denied'); } });
  expect(loadGameId()).toBeNull();
  expect(storeGameId('adv_next')).toBe(false);
});

test('a full storage device reports that the pointer could not be saved', () => {
  storage.setItem.mockImplementation(() => { throw new Error('quota exceeded'); });
  expect(storeGameId('adv_next')).toBe(false);
});
