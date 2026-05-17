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
  getGraphLevelUpOptions,
  initGraphSession,
  listProfiles,
  requestGraphIntro,
  rollGraphPending,
  sendGraphAction,
  sendGraphCombatCommand,
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
            outcome: 'neutral',
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
    expect(result.outcome).toBe('neutral');
  });

  test('posts combat commands to the graph combat endpoint', async () => {
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

    const result = await sendGraphCombatCommand('game-1', {
      command: 'precise',
      target_id: 'enemy_01',
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/combat/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ command: 'precise', target_id: 'enemy_01' }),
      }),
    );
    expect(result.status).toBe('executed');
  });

  test('streams graph action narration deltas before the final payload', async () => {
    const onNarrationDelta = jest.fn();
    const response = {
      game_id: 'game-1',
      state: graphState(),
      status: 'executed',
      outcome: 'success',
      message: null,
    };
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({ type: 'result', payload: response }),
        JSON.stringify({ type: 'narration_delta', text: '검이 ' }),
        JSON.stringify({ type: 'narration_delta', text: '허공을 가릅니다.' }),
        JSON.stringify({
          type: 'final',
          payload: response,
        }),
      ]),
    );

    const result = await sendGraphAction('game-1', { verb: 'attack', what: 'dummy' }, { onNarrationDelta });

    expect(onNarrationDelta).toHaveBeenNthCalledWith(1, '검이 ', 'success');
    expect(onNarrationDelta).toHaveBeenNthCalledWith(2, '허공을 가릅니다.', 'success');
    expect(result.outcome).toBe('success');
  });

  test('tags restored graph sessions as graph runtime payloads', async () => {
    const state = graphState();
    state.place = {
      id: 'town',
      name: '광장',
      description: '',
      exits: [{ id: 'watch', name: '망루', description: '' }],
      items: [],
      targets: [
        {
          id: 'edrik_chief',
          name: '에드릭',
          kind: 'npc',
          alive: true,
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

  test('requests initial graph narration through the graph intro stream endpoint', async () => {
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

    await requestGraphIntro('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/intro/stream',
      expect.objectContaining({
        method: 'POST',
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('streams graph intro narration deltas before the final payload', async () => {
    const onNarrationDelta = jest.fn();
    const response = {
      game_id: 'game-1',
      state: graphState(),
      status: 'executed',
      outcome: 'success',
      message: null,
    };
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({ type: 'result', payload: response }),
        JSON.stringify({ type: 'narration_delta', text: '문이 ' }),
        JSON.stringify({ type: 'narration_delta', text: '열립니다.' }),
        JSON.stringify({
          type: 'final',
          payload: response,
        }),
      ]),
    );

    const result = await requestGraphIntro('game-1', { onNarrationDelta });

    expect(onNarrationDelta).toHaveBeenNthCalledWith(1, '문이 ', 'success');
    expect(onNarrationDelta).toHaveBeenNthCalledWith(2, '열립니다.', 'success');
    expect(result.status).toBe('executed');
    expect(result.outcome).toBe('success');
  });

  test('falls back to the plain graph intro endpoint when the stream route is unavailable', async () => {
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

    await requestGraphIntro('game-1');

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      'https://api.example.test/session/game-1/graph/intro/stream',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
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
        }),
        signal: expect.any(AbortSignal),
      }),
    );
  });

  test('streams graph text input narration deltas before the final payload', async () => {
    const onNarrationDelta = jest.fn();
    const response = {
      game_id: 'game-1',
      state: graphState(),
      status: 'executed',
      outcome: 'success',
      message: null,
    };
    fetch.mockResolvedValueOnce(
      streamResponse([
        JSON.stringify({ type: 'result', payload: response }),
        JSON.stringify({ type: 'narration_delta', text: '당신은 ' }),
        JSON.stringify({ type: 'narration_delta', text: '문을 봅니다.' }),
        JSON.stringify({
          type: 'final',
          payload: response,
        }),
      ]),
    );

    const events: string[] = [];
    const result = await sendGraphInput('game-1', '문을 본다', {
      onResult: () => { events.push('result'); },
      onNarrationDelta: (text, outcome) => {
        events.push('delta');
        onNarrationDelta(text, outcome);
      },
    });

    expect(onNarrationDelta).toHaveBeenNthCalledWith(1, '당신은 ', 'success');
    expect(onNarrationDelta).toHaveBeenNthCalledWith(2, '문을 봅니다.', 'success');
    expect(events).toEqual(['result', 'delta', 'delta']);
    expect(result.status).toBe('executed');
    expect(result.outcome).toBe('success');
  });

  test('uses server graph suggestions from an action response', async () => {
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
                label: '북문으로 이동합니다',
                input_text: '북문으로 이동합니다',
                intent: null,
                action: null,
              },
              {
                label: '발자국을 자세히 살펴봅니다',
                input_text: '발자국을 자세히 살펴봅니다',
                intent: null,
                action: null,
              },
            ],
          },
        }),
      ]),
    );

    const result = await sendGraphInput('game-1', '북문 이야기를 듣는다');

    expect(result.suggestions).toEqual([
      { label: '북문으로 이동합니다', inputText: '북문으로 이동합니다', intent: null },
      { label: '발자국을 자세히 살펴봅니다', inputText: '발자국을 자세히 살펴봅니다', intent: null },
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
      growth: { kind: 'max_hp' },
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/level_up',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          growth: { kind: 'max_hp' },
        }),
      }),
    );
    expect(result.pendingConfirmation).toBeNull();
  });

  test('loads graph level-up options from the options endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        choices: [{
          id: 'learn_skill:skill_gen_attack_1',
          label: '그림자 찌르기 습득',
          description: '공격 DC를 낮춘다.',
          growth: {
            kind: 'learn_skill',
            skill_id: 'skill_gen_attack_1',
            skill: {
              id: 'skill_gen_attack_1',
              name: '그림자 찌르기',
              description: '공격 DC를 낮춘다.',
              action: 'attack',
              bonus: 2,
              mp_cost: 2,
            },
          },
        }],
      }),
    });

    const result = await getGraphLevelUpOptions('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/level_up/options',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result[0].growth.kind).toBe('learn_skill');
  });

  test('posts pending roll choices to the graph roll stream endpoint', async () => {
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

    const result = await rollGraphPending('game-1', {
      roll_id: 'roll-1',
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/roll/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          roll_id: 'roll-1',
        }),
      }),
    );
    expect(result.pendingRoll).toBeNull();
    expect(result.outcome).toBe('neutral');
  });

  test('falls back to the plain graph roll endpoint when the stream route is unavailable', async () => {
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

    await rollGraphPending('game-1', {
      roll_id: 'roll-1',
    });

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      'https://api.example.test/session/game-1/graph/roll/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          roll_id: 'roll-1',
        }),
      }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      'https://api.example.test/session/game-1/graph/roll',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          roll_id: 'roll-1',
        }),
      }),
    );
  });
});
