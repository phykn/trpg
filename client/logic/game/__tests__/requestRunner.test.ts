import type { FrontState, GraphActionClientResponse } from '@/services/wire';
import {
  abortGraphActionRequest,
  runGraphActionRequestOnce,
  type GraphActionRequestRuntime,
} from '../requestRunner';

function response(gameId: string): GraphActionClientResponse {
  return {
    game_id: gameId,
    state: {} as FrontState,
    pendingConfirmation: null,
    pendingRoll: null,
    suggestions: ['next'],
  };
}

function runtime(activeGameId = 'game-1'): GraphActionRequestRuntime {
  return {
    requestInFlightRef: { current: false },
    abortControllerRef: { current: null },
    requestGenerationRef: { current: 0 },
    setRequestInFlight: jest.fn(),
    setErrorMessage: jest.fn(),
    setLog: jest.fn(),
    setSuggestions: jest.fn(),
    applyState: jest.fn(),
    isActiveGameId: (gameId) => gameId === activeGameId,
  };
}

describe('runGraphActionRequestOnce', () => {
  test('ignores a response for a game that is no longer active', async () => {
    const rt = runtime('game-2');

    await runGraphActionRequestOnce(() => Promise.resolve(response('game-1')), rt);

    expect(rt.applyState).not.toHaveBeenCalled();
    expect(rt.setLog).not.toHaveBeenCalled();
    expect(rt.setSuggestions).toHaveBeenCalledWith([]);
    expect(rt.setSuggestions).not.toHaveBeenCalledWith(['next']);
  });

  test('aborts the current request without surfacing an error', async () => {
    const rt = runtime('game-1');
    const abortError = Object.assign(new Error('aborted'), { name: 'AbortError' });

    const pending = runGraphActionRequestOnce(
      (signal) =>
        new Promise<GraphActionClientResponse>((_, reject) => {
          signal.addEventListener('abort', () => reject(abortError));
        }),
      rt,
    );

    abortGraphActionRequest(rt);
    await pending;

    expect(rt.applyState).not.toHaveBeenCalled();
    expect(rt.setErrorMessage).toHaveBeenCalledTimes(1);
    expect(rt.setErrorMessage).toHaveBeenCalledWith(null);
    expect(rt.setRequestInFlight).toHaveBeenLastCalledWith(false);
  });
});
