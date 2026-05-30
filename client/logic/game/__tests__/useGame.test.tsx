// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act } from 'react-test-renderer';

import { ko } from '@/locale/ko';
import { useGame, type Game } from '../useGame';
import { getGraphSessionById, loadStoredGameId } from '@/services';

jest.mock('@/services', () => ({
  clearAllForGame: jest.fn(),
  clearStoredGameId: jest.fn(),
  confirmGraphAction: jest.fn(),
  getGraphLevelUpOptions: jest.fn(),
  getGraphSessionById: jest.fn(),
  initGraphSession: jest.fn(),
  loadStoredGameId: jest.fn(),
  loadSuggestions: jest.fn(() => []),
  storeGameId: jest.fn(),
  storeSuggestions: jest.fn(),
  requestGraphIntro: jest.fn(),
  rollGraphPending: jest.fn(),
  sendGraphAction: jest.fn(),
  sendGraphCombatCommand: jest.fn(),
  sendGraphInput: jest.fn(),
  sendGraphLevelUp: jest.fn(),
}));

function Harness({ onState }: { onState: (game: Game) => void }) {
  const game = useGame();
  onState(game);
  return null;
}

describe('useGame', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('shows a localized retry message when stored game restore cannot reach the server', async () => {
    (loadStoredGameId as jest.Mock).mockReturnValue('game-1');
    (getGraphSessionById as jest.Mock).mockRejectedValue(new TypeError('Failed to fetch'));
    let current: Game | null = null;

    await act(async () => {
      renderer.create(<Harness onState={(game) => { current = game; }} />);
      await Promise.resolve();
    });

    const game = current as unknown as Game;
    expect(game.status).toBe('error');
    expect(game.errorMessage).toBe(ko.error.requestInterrupted);
  });
});
