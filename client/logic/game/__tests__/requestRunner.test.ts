import type { FrontState, GraphActionClientResponse } from '@/services/wire';
import type { LogEntry } from '@/logic/log';
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
    outcome: 'neutral',
    suggestions: [{ label: '다음', inputText: '다음 행동을 합니다' }],
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
  test('adds optimistic log entries before the request resolves', async () => {
    const rt = runtime('game-1');
    let resolveResponse: (value: GraphActionClientResponse) => void = () => {};

    const pending = runGraphActionRequestOnce(
      () =>
        new Promise<GraphActionClientResponse>((resolve) => {
          resolveResponse = resolve;
        }),
      rt,
      [{ kind: 'player', text: '문을 두드립니다' }],
    );

    expect(rt.setLog).toHaveBeenCalledTimes(1);
    const updater = (rt.setLog as jest.Mock).mock.calls[0][0] as (
      current: LogEntry[],
    ) => LogEntry[];
    const nextLog = updater([{ id: 1, kind: 'gm', text: '앞에는 문이 있습니다.' }]);
    expect(nextLog).toEqual([
      { id: 1, kind: 'gm', text: '앞에는 문이 있습니다.' },
      expect.objectContaining({
        kind: 'player',
        text: '문을 두드립니다',
      }),
    ]);
    expect((nextLog[1] as { id: number }).id).toBeLessThan(0);

    resolveResponse(response('game-1'));
    await pending;
  });

  test('streams narration into one temporary gm log entry before final state', async () => {
    const rt = runtime('game-1');

    await runGraphActionRequestOnce(
      async (_signal, events) => {
        events.onNarrationDelta('당신은 ', 'success');
        events.onNarrationDelta('문을 봅니다.', 'success');
        return response('game-1');
      },
      rt,
      [{ kind: 'player', text: '문을 본다' }],
    );

    expect(rt.setLog).toHaveBeenCalledTimes(3);
    const appendPlayer = (rt.setLog as jest.Mock).mock.calls[0][0] as (
      current: LogEntry[],
    ) => LogEntry[];
    const appendFirstDelta = (rt.setLog as jest.Mock).mock.calls[1][0] as (
      current: LogEntry[],
    ) => LogEntry[];
    const appendSecondDelta = (rt.setLog as jest.Mock).mock.calls[2][0] as (
      current: LogEntry[],
    ) => LogEntry[];

    const withPlayer = appendPlayer([]);
    const withFirstDelta = appendFirstDelta(withPlayer);
    const withSecondDelta = appendSecondDelta(withFirstDelta);

    expect(withFirstDelta).toEqual([
      expect.objectContaining({ kind: 'player', text: '문을 본다' }),
      expect.objectContaining({ kind: 'gm', text: '당신은 ', outcome: 'success' }),
    ]);
    expect(withSecondDelta).toEqual([
      expect.objectContaining({ kind: 'player', text: '문을 본다' }),
      expect.objectContaining({ kind: 'gm', text: '당신은 문을 봅니다.', outcome: 'success' }),
    ]);
    expect(withSecondDelta[1].id).toBe(withFirstDelta[1].id);
  });

  test('applies result state before the final response updates suggestions', async () => {
    const rt = runtime('game-1');
    const resultResponse = response('game-1');
    const finalResponse = response('game-1');
    resultResponse.state = { result: true } as unknown as FrontState;
    finalResponse.state = { final: true } as unknown as FrontState;

    await runGraphActionRequestOnce(
      async (_signal, events) => {
        (events as { onResult: (value: GraphActionClientResponse) => void }).onResult(resultResponse);
        return finalResponse;
      },
      rt,
    );

    expect(rt.applyState).toHaveBeenNthCalledWith(1, resultResponse.state, 'game-1');
    expect(rt.applyState).toHaveBeenNthCalledWith(2, finalResponse.state, 'game-1');
    expect(rt.setSuggestions).toHaveBeenLastCalledWith(finalResponse.suggestions);
  });

  test('ignores a response for a game that is no longer active', async () => {
    const rt = runtime('game-2');

    await runGraphActionRequestOnce(() => Promise.resolve(response('game-1')), rt);

    expect(rt.applyState).not.toHaveBeenCalled();
    expect(rt.setLog).not.toHaveBeenCalled();
    expect(rt.setSuggestions).toHaveBeenCalledWith([]);
    expect(rt.setSuggestions).not.toHaveBeenCalledWith([
      { label: '다음', inputText: '다음 행동을 합니다' },
    ]);
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

  test('removes temporary streamed narration and shows a friendly retry message on network failure', async () => {
    const rt = runtime('game-1');

    await runGraphActionRequestOnce(
      async (_signal, events) => {
        events.onNarrationDelta('루카가 입을 엽니다.', 'neutral');
        throw new Error('network error');
      },
      rt,
      [{ kind: 'player', text: '루카에게 접근합니다' }],
    );

    expect(rt.setLog).toHaveBeenCalledTimes(3);
    const appendPlayer = (rt.setLog as jest.Mock).mock.calls[0][0] as (
      current: LogEntry[],
    ) => LogEntry[];
    const appendDelta = (rt.setLog as jest.Mock).mock.calls[1][0] as (
      current: LogEntry[],
    ) => LogEntry[];
    const removeDelta = (rt.setLog as jest.Mock).mock.calls[2][0] as (
      current: LogEntry[],
    ) => LogEntry[];

    const withPlayer = appendPlayer([]);
    const withDelta = appendDelta(withPlayer);
    const afterFailure = removeDelta(withDelta);

    expect(withDelta).toEqual([
      expect.objectContaining({ kind: 'player', text: '루카에게 접근합니다' }),
      expect.objectContaining({ kind: 'gm', text: '루카가 입을 엽니다.' }),
    ]);
    expect(afterFailure).toEqual([
      expect.objectContaining({ kind: 'player', text: '루카에게 접근합니다' }),
    ]);
    expect(rt.setErrorMessage).toHaveBeenLastCalledWith(
      '요청이 끊겼습니다. 같은 행동을 다시 시도해 주세요.',
    );
  });
});
