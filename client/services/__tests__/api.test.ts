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

describe('graph API helpers', () => {
  beforeEach(() => {
    fetch.mockReset();
  });

  test('posts explicit graph actions to the graph turn endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
        status: 'confirmation_required',
        message: null,
      }),
    });

    const result = await sendGraphAction('game-1', {
      verb: 'transfer',
      what: 'quest_01',
      how: 'accept',
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/turn',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          action: { verb: 'transfer', what: 'quest_01', how: 'accept' },
        }),
      }),
    );
    expect(result.status).toBe('confirmation_required');
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
      '에드릭에게 말을 겁니다',
      '망루로 이동합니다',
      '주변을 살펴봅니다',
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

    expect(fetch).toHaveBeenCalledWith(
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
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state: graphState(),
        status: 'executed',
        message: null,
      }),
    });

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
