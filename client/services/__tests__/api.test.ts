import type { GraphFrontState } from '../wire';

process.env.EXPO_PUBLIC_API_URL = 'https://api.example.test';
process.env.EXPO_PUBLIC_API_USER = 'tester';
process.env.EXPO_PUBLIC_API_PASS = 'secret';

jest.mock('expo/fetch', () => ({
  fetch: jest.fn(),
}));

const { fetch } = require('expo/fetch') as { fetch: jest.Mock };
const {
  getGraphSessionById,
  initGraphSession,
  listProfiles,
  requestGraphIntro,
  rollGraphPending,
  sendGraphAction,
  sendGraphInput,
  sendGraphLevelUp,
} = require('../api') as typeof import('../api');

const graphState = (): GraphFrontState => ({
  hero: {
    id: 'player_01',
    name: '테스터',
    level: 1,
    exp: 0,
    expMax: 20,
    canLevelUp: false,
    gold: 0,
    resources: {
      hp: { current: 30, maximum: 30, state: 'healthy' },
      mp: { current: 10, maximum: 10, state: 'fresh' },
    },
    stats: {
      body: 3,
      agility: 2,
      mind: 1,
      presence: 0,
    },
    equipment: {
      weapon: null,
      armor: null,
      accessory: null,
    },
    inventory: [],
    status: [],
    skills: [],
  },
  quest: null,
  questOffers: [],
  place: null,
  combat: null,
  pendingConfirmation: null,
  pendingRoll: null,
  log: [],
});

function streamResponse(lines: string[]) {
  const chunks = lines.map((line) => new TextEncoder().encode(`${line}\n`));
  let index = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: jest.fn(async () => {
          const value = chunks[index];
          index += 1;
          return value ? { done: false, value } : { done: true, value: undefined };
        }),
        releaseLock: jest.fn(),
      }),
    },
  };
}

describe('graph API helpers', () => {
  beforeEach(() => {
    fetch.mockReset();
  });

  test('posts explicit graph actions to the graph turn endpoint', async () => {
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'confirmation_required',
            message: null,
          },
        }),
      ]),
    );

    const result = await sendGraphAction('game-1', {
      verb: 'transfer',
      what: 'quest_01',
      how: 'accept',
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/turn/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          action: { verb: 'transfer', what: 'quest_01', how: 'accept' },
        }),
      }),
    );
    expect(result.status).toBe('confirmation_required');
  });

  test('streams graph action narration deltas before the final payload', async () => {
    const onNarrationDelta = jest.fn();
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({ type: 'delta', text: '검이 ' }),
        JSON.stringify({ type: 'delta', text: '허공을 가릅니다.' }),
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'executed',
            message: null,
          },
        }),
      ]),
    );

    await sendGraphAction('game-1', { verb: 'attack', what: 'dummy' }, { onNarrationDelta });

    expect(onNarrationDelta).toHaveBeenNthCalledWith(1, '검이 ');
    expect(onNarrationDelta).toHaveBeenNthCalledWith(2, '허공을 가릅니다.');
  });

  test('tags restored graph sessions as graph runtime payloads', async () => {
    const state = graphState();
    state.place = {
      id: 'town',
      name: '광장',
      description: '',
      exits: [{ id: 'watch', name: '망루', description: '' }],
      targets: [
        {
          id: 'edrik_chief',
          name: '에드릭',
          kind: 'npc',
          hp: { current: 20, maximum: 20, state: 'healthy' },
          level: 1,
          raceJob: '',
          gender: '',
          role: '',
          gold: 0,
          stats: {},
          equipment: { weapon: null, armor: null, accessory: null },
          inventory: [],
          skills: [],
          status: [],
        },
      ],
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state,
      }),
    });

    const result = await getGraphSessionById('game-1');

    expect(result?.suggestions).toEqual([
      { label: '에드릭에게 말을 겁니다', inputText: '에드릭에게 말을 겁니다' },
      { label: '망루로 이동합니다', inputText: '망루로 이동합니다' },
      { label: '주변을 살펴봅니다', inputText: '주변을 살펴봅니다' },
    ]);
  });

  test('loads profiles with an abortable request signal', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          id: 'dev_test',
          name: '개발 원턴 테스트',
          description: '',
          races: [{ id: 'human', name: '인간', description: '' }],
        },
      ],
    });

    await listProfiles();

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/profiles',
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('posts graph init with an abortable request signal', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
      }),
    });

    await initGraphSession({
      profile: 'dev_test',
      player: { name: '테스터', race_id: 'human', gender: 'male' },
      locale: 'ko',
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/graph/init',
      expect.objectContaining({
        method: 'POST',
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('requests initial graph narration through the graph intro endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
        status: 'executed',
        message: null,
      }),
    });

    await requestGraphIntro('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/intro',
      expect.objectContaining({
        method: 'POST',
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('includes server error detail in graph init failures', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({ detail: 'profile not found: missing' }),
    });

    await expect(
      initGraphSession({
        profile: 'missing',
        player: { name: '테스터', race_id: 'human', gender: 'male' },
        locale: 'ko',
      }),
    ).rejects.toThrow('profile not found: missing');
  });

  test('posts graph text input with an abortable request signal', async () => {
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'executed',
            message: null,
          },
        }),
      ]),
    );

    await sendGraphInput('game-1', '마을 주민에게 말을 건다');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/input/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          player_input: '마을 주민에게 말을 건다',
          think: false,
        }),
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('streams graph text input narration deltas before the final payload', async () => {
    const onNarrationDelta = jest.fn();
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({ type: 'delta', text: '당신은 ' }),
        JSON.stringify({ type: 'delta', text: '문을 봅니다.' }),
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'executed',
            message: null,
          },
        }),
      ]),
    );

    const result = await sendGraphInput('game-1', '문을 본다', { onNarrationDelta });

    expect(onNarrationDelta).toHaveBeenNthCalledWith(1, '당신은 ');
    expect(onNarrationDelta).toHaveBeenNthCalledWith(2, '문을 봅니다.');
    expect(result.status).toBe('executed');
  });

  test('uses server graph suggestions when an action response includes legacy strings', async () => {
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'executed',
            message: null,
            suggestions: ['북문으로 이동합니다', '발자국을 자세히 살펴봅니다'],
          },
        }),
      ]),
    );

    const result = await sendGraphInput('game-1', '북문 이야기를 듣는다');

    expect(result.suggestions).toEqual([
      { label: '북문으로 이동합니다', inputText: '북문으로 이동합니다' },
      { label: '발자국을 자세히 살펴봅니다', inputText: '발자국을 자세히 살펴봅니다' },
    ]);
  });

  test('uses structured server graph suggestions as short chips with longer input', async () => {
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'executed',
            message: null,
            suggestions: [
              {
                label: '북문으로',
                input_text: '북문으로 이동합니다',
                intent: 'move',
                action: null,
              },
            ],
          },
        }),
      ]),
    );

    const result = await sendGraphInput('game-1', '북문 이야기를 듣는다');

    expect(result.suggestions).toEqual([
      { label: '북문으로', inputText: '북문으로 이동합니다', intent: 'move' },
    ]);
  });

  test('falls back to the plain graph input endpoint when the stream route is unavailable', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'not found' }),
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
        status: 'executed',
        message: null,
      }),
    });

    await sendGraphInput('game-1', '마을 주민에게 말을 건다');

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      'https://api.example.test/session/game-1/graph/input/stream',
      expect.objectContaining({
        method: 'POST',
      }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      'https://api.example.test/session/game-1/graph/input',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          player_input: '마을 주민에게 말을 건다',
          think: false,
        }),
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('links caller abort signals to graph requests', async () => {
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({
          type: 'final',
          payload: {
            game_id: 'game-1',
            state: graphState(),
            status: 'executed',
            message: null,
          },
        }),
      ]),
    );

    const controller = new AbortController();
    const promise = sendGraphInput('game-1', '마을 주민에게 말을 건다', {
      signal: controller.signal,
    });
    const signal = fetch.mock.calls[0][1].signal as AbortSignal;

    controller.abort();

    expect(signal.aborted).toBe(true);
    await promise;
  });

  test('posts graph level-up choices to the graph level-up endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
        status: null,
        message: null,
      }),
    });

    const result = await sendGraphLevelUp('game-1', {
      stat_up: 'body',
      skill_id: null,
      think: false,
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/level_up',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          stat_up: 'body',
          skill_id: null,
          think: false,
        }),
      }),
    );
    expect(result.pendingConfirmation).toBeNull();
  });

  test('posts pending roll choices to the graph roll endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
        status: 'executed',
        message: null,
      }),
    });

    const result = await rollGraphPending('game-1', {
      roll_id: 'roll-1',
      think: false,
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/roll',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          roll_id: 'roll-1',
          think: false,
        }),
      }),
    );
    expect(result.pendingRoll).toBeNull();
  });
});
