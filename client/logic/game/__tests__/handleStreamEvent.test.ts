import { handleStreamEvent, type StreamHandlers } from '../handleStreamEvent';

const makeHandlers = (): jest.Mocked<StreamHandlers> => ({
  setPending: jest.fn(),
  clearPending: jest.fn(),
  appendStreamingText: jest.fn(),
  clearStreamingText: jest.fn(),
  upsertLogEntry: jest.fn(),
  applyState: jest.fn(),
  setSuggestions: jest.fn(),
  setErrorMessage: jest.fn(),
});

describe('handleStreamEvent', () => {
  test('narrative_delta forwards text to appendStreamingText', () => {
    const h = makeHandlers();
    handleStreamEvent({ type: 'narrative_delta', data: { text: '안녕하세요' } }, h);
    expect(h.appendStreamingText).toHaveBeenCalledWith('안녕하세요');
    expect(h.appendStreamingText).toHaveBeenCalledTimes(1);
  });

  test('pending_check forwards payload to setPending', () => {
    const h = makeHandlers();
    const payload = {
      kind: 'stat' as const,
      dc: 12,
      stat: 'DEX',
      stat_label: '민첩',
      stat_value: 14,
      mod: 2,
      required_roll: 10,
      tier: { value: 1, max: 3, label: '초급' },
      target: '문',
      reason: '잠금 해제',
    };
    handleStreamEvent({ type: 'pending_check', data: payload }, h);
    expect(h.setPending).toHaveBeenCalledWith(payload);
  });

  test('log_entry kind=roll triggers clearPending and not clearStreamingText', () => {
    const h = makeHandlers();
    const entry = {
      id: 1,
      kind: 'roll' as const,
      check: 'DEX',
      roll: 15,
      margin: 3,
      result: 'success' as const,
      bonus_breakdown: [],
    };
    handleStreamEvent({ type: 'log_entry', data: entry }, h);
    expect(h.upsertLogEntry).toHaveBeenCalledWith(entry);
    expect(h.clearPending).toHaveBeenCalledTimes(1);
    expect(h.clearStreamingText).not.toHaveBeenCalled();
  });

  test('log_entry kind=gm triggers clearStreamingText and not clearPending', () => {
    const h = makeHandlers();
    const entry = { id: 2, kind: 'gm' as const, text: '문이 열렸습니다.' };
    handleStreamEvent({ type: 'log_entry', data: entry }, h);
    expect(h.upsertLogEntry).toHaveBeenCalledWith(entry);
    expect(h.clearStreamingText).toHaveBeenCalledTimes(1);
    expect(h.clearPending).not.toHaveBeenCalled();
  });

  test('log_entry kind=player only upserts (no clears)', () => {
    const h = makeHandlers();
    const entry = { id: 3, kind: 'player' as const, text: '문을 열어본다' };
    handleStreamEvent({ type: 'log_entry', data: entry }, h);
    expect(h.upsertLogEntry).toHaveBeenCalledWith(entry);
    expect(h.clearPending).not.toHaveBeenCalled();
    expect(h.clearStreamingText).not.toHaveBeenCalled();
  });

  test('state applies state and clears streaming text', () => {
    const h = makeHandlers();
    const state = { hero: {}, log: [], pendingCheck: null } as never;
    handleStreamEvent({ type: 'state', data: state }, h);
    expect(h.applyState).toHaveBeenCalledWith(state);
    expect(h.clearStreamingText).toHaveBeenCalledTimes(1);
  });

  test('error pulls message from ErrorPayload into setErrorMessage', () => {
    const h = makeHandlers();
    handleStreamEvent(
      {
        type: 'error',
        data: { code: 'LLMUnavailable', message: '이야기꾼이 잠시 길을 잃었습니다.' },
      },
      h,
    );
    expect(h.setErrorMessage).toHaveBeenCalledWith('이야기꾼이 잠시 길을 잃었습니다.');
  });

  test('suggestions forwards items', () => {
    const h = makeHandlers();
    handleStreamEvent({ type: 'suggestions', data: { items: ['도망친다', '맞선다'] } }, h);
    expect(h.setSuggestions).toHaveBeenCalledWith(['도망친다', '맞선다']);
  });

  test('judge / combat_* / done are observability-only (no handlers fire)', () => {
    const h = makeHandlers();
    handleStreamEvent(
      { type: 'judge', data: { judge_kind: 'refuse', refuse: { category: 'out_of_game', message_hint: 'y' } } },
      h,
    );
    handleStreamEvent(
      {
        type: 'combat_start',
        data: { turn_order: ['player'], round: 1, enemy_ids: ['enemy_1'] },
      },
      h,
    );
    handleStreamEvent(
      {
        type: 'combat_turn',
        data: { actor: 'player', action: 'attack', round: 1 },
      },
      h,
    );
    handleStreamEvent({ type: 'combat_end', data: { outcome: 'victory' } }, h);
    handleStreamEvent({ type: 'done', data: {} }, h);

    for (const fn of Object.values(h)) {
      expect(fn).not.toHaveBeenCalled();
    }
  });
});
