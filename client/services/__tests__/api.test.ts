import type { GraphFrontState } from '../wire';

process.env.EXPO_PUBLIC_API_URL = 'https://api.example.test';
process.env.EXPO_PUBLIC_API_USER = 'tester';
process.env.EXPO_PUBLIC_API_PASS = 'secret';

jest.mock('expo/fetch', () => ({
  fetch: jest.fn(),
}));

const { fetch } = require('expo/fetch') as { fetch: jest.Mock };
const { getGraphSessionById, sendGraphAction, sendGraphInput, sendGraphLevelUp } = require('../api') as typeof import('../api');

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
      '에드릭에게 말을 건다',
      '망루로 이동한다',
      '주변을 살펴본다',
    ]);
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
});
