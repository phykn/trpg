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
  getStoryDebt,
  getStoryContract,
  getStoryGraph,
  getStoryPatchEntries,
  getStoryPatchTimeline,
  initGraphSession,
  listProfiles,
  previewStoryPatch,
  previewStoryContract,
  replayStoryPrompt,
  requestGraphIntro,
  rollbackStoryPatch,
  rollGraphPending,
  sendGraphAction,
  sendGraphCombatCommand,
  sendGraphInput,
  sendGraphLevelUp,
  updateStoryContract,
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
  chapter: null,
  scenarioCompleted: false,
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
      command: 'attack',
      target: 'enemy_01',
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/graph/combat/stream',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ command: 'attack', target: 'enemy_01' }),
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

  test('does not derive fallback suggestions when restored graph session omits suggestions', async () => {
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
          canAttack: true,
          level: 1,
          raceJob: '',
          gender: '',
          role: '',
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

    expect(result?.suggestions).toEqual([]);
  });

  test('does not derive fallback suggestions when server sends an empty list', async () => {
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
          canAttack: true,
          level: 1,
          raceJob: '',
          gender: '',
          role: '',
        },
      ],
    };
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        state,
        suggestions: [],
      }),
    });

    const result = await getGraphSessionById('game-1');

    expect(result?.suggestions).toEqual([]);
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

  test('uses server error detail without transport prefix in action failures', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        detail: '지금은 그 장소로 이동할 수 없습니다. 화면에 보이는 이동 경로를 선택해야 합니다.',
      }),
    });

    await expect(
      sendGraphAction('game-1', { verb: 'move', to: 'missing_place' }),
    ).rejects.toThrow(/^지금은 그 장소로 이동할 수 없습니다\. 화면에 보이는 이동 경로를 선택해야 합니다\.$/);
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

  test('localizes internal server suggestion labels by intent', async () => {
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
                label: 'inspect',
                input_text: '발자국을 자세히 살펴봅니다',
                intent: 'inspect',
                action: null,
              },
              {
                label: 'move',
                input_text: '북문으로 이동합니다',
                intent: 'move',
                action: null,
              },
            ],
          },
        }),
      ]),
    );

    const result = await sendGraphInput('game-1', '주변을 확인한다');

    expect(result.suggestions).toEqual([
      { label: '살펴보기', inputText: '발자국을 자세히 살펴봅니다', intent: 'inspect' },
      { label: '이동', inputText: '북문으로 이동합니다', intent: 'move' },
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

  test('loads generated story patch entries from the dev ledger endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        entries: [
          {
            turn: 2,
            status: 'accepted',
            intent_kind: 'clue_candidate',
            reason: 'found',
            patches: [{ op: 'add_clue', id: 'clue_wet_ticket' }],
            rejected_reasons: [],
            changed_node_ids: ['clue_wet_ticket'],
            changed_edge_ids: ['has_knowledge:loc_01:clue_wet_ticket'],
          },
        ],
      }),
    });

    const result = await getStoryPatchEntries('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/patches',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result.entries[0].status).toBe('accepted');
    expect(result.entries[0].changedNodeIds).toEqual(['clue_wet_ticket']);
  });

  test('loads generated story timeline from the dev timeline endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        entries: [],
      }),
    });

    await getStoryPatchTimeline('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/timeline',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  test('loads generated story debt from the dev debt endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        debt: {
          unresolved_clues: [
            {
              id: 'clue_wet_ticket',
              title: '젖은 표',
              turn: 2,
              reason: 'generated clue is not marked resolved',
            },
          ],
          orphan_characters: [],
          orphan_items: [],
          dangling_quest_beats: [],
        },
      }),
    });

    const result = await getStoryDebt('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/debt',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result.debt.unresolvedClues[0].id).toBe('clue_wet_ticket');
  });

  test('loads raw story graph from the dev graph endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        graph: {
          nodes: {
            loc_01: {
              id: 'loc_01',
              type: 'location',
              properties: { name: '항구' },
            },
          },
          edges: {},
        },
      }),
    });

    const result = await getStoryGraph('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/dev/graph',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result.graph.nodes.loc_01.type).toBe('location');
  });

  test('loads active story contract from the dev contract endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        contract: {
          id: 'white_isle',
          world: { title: '흰섬으로 가는 안개 바다', locale: 'ko' },
          fixed: [],
          forbid: [],
          tone: { register: '합니다체', person: 'second' },
          budgets: { patches_per_turn: 1, new_terms_per_turn: 1 },
          allowed_ops: ['add_clue'],
          stability_defaults: { add_clue: 'scene' },
        },
      }),
    });

    const result = await getStoryContract('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/dev/contract',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(result.contract.id).toBe('white_isle');
  });

  test('previews a story contract edit through the dev endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        ok: true,
        reasons: [],
        contract: {
          id: 'white_isle',
          world: { title: '흰섬으로 가는 안개 바다', locale: 'ko' },
          fixed: [],
          forbid: [],
          tone: { register: '합니다체', person: 'second' },
          budgets: { patches_per_turn: 1, new_terms_per_turn: 1 },
          allowed_ops: ['add_clue'],
          stability_defaults: { add_clue: 'scene' },
        },
      }),
    });

    const result = await previewStoryContract('game-1', {
      id: 'white_isle',
      allowed_ops: ['add_clue'],
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/dev/preview_contract',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          contract: {
            id: 'white_isle',
            allowed_ops: ['add_clue'],
          },
        }),
      }),
    );
    expect(result.ok).toBe(true);
  });

  test('updates the session story contract through the dev endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        contract: {
          id: 'white_isle_override',
          world: { title: '흰섬으로 가는 안개 바다', locale: 'ko' },
          fixed: [],
          forbid: [],
          tone: { register: '합니다체', person: 'second' },
          budgets: { patches_per_turn: 1, new_terms_per_turn: 1 },
          allowed_ops: ['add_clue'],
          stability_defaults: { add_clue: 'scene' },
        },
      }),
    });

    const result = await updateStoryContract('game-1', {
      id: 'white_isle_override',
      allowed_ops: ['add_clue'],
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/dev/contract',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          contract: {
            id: 'white_isle_override',
            allowed_ops: ['add_clue'],
          },
        }),
      }),
    );
    expect(result.contract.id).toBe('white_isle_override');
  });

  test('rolls back the latest generated story patch through the dev endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        entry: {
          turn: 3,
          status: 'rolled_back',
          intent_kind: 'clue_candidate',
          reason: 'rolled back accepted story patch',
          patches: [{ op: 'add_clue', id: 'clue_wet_ticket' }],
          rejected_reasons: [],
          changed_node_ids: ['clue_wet_ticket'],
          changed_edge_ids: ['has_knowledge:loc_01:clue_wet_ticket'],
        },
      }),
    });

    const result = await rollbackStoryPatch('game-1');

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/rollback',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(result.entry.status).toBe('rolled_back');
    expect(result.entry.changedNodeIds).toEqual(['clue_wet_ticket']);
  });

  test('previews a generated story patch through the dev endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        ok: true,
        reasons: [],
        changed_node_ids: ['clue_preview'],
        changed_edge_ids: ['has_knowledge:loc_01:clue_preview'],
      }),
    });

    const result = await previewStoryPatch('game-1', {
      reason: 'preview',
      patches: [{ op: 'add_clue', id: 'clue_preview' }],
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/dev/preview_patch',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          proposal: {
            reason: 'preview',
            patches: [{ op: 'add_clue', id: 'clue_preview' }],
          },
        }),
      }),
    );
    expect(result.changedNodeIds).toEqual(['clue_preview']);
  });

  test('replays the story writer prompt through the dev endpoint', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        game_id: 'game-1',
        agent: 'story_write',
        intent: { kind: 'clue_candidate', reason: 'perception action' },
        system_prompt: 'write only patches',
        user_payload: {
          player_input: '표를 살핍니다.',
          action: { verb: 'perceive', what: 'ticket' },
        },
      }),
    });

    const result = await replayStoryPrompt('game-1', {
      player_input: '표를 살핍니다.',
      action: { verb: 'perceive', what: 'ticket' },
    });

    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.test/session/game-1/story/dev/replay_prompt',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          player_input: '표를 살핍니다.',
          action: { verb: 'perceive', what: 'ticket' },
        }),
      }),
    );
    expect(result.agent).toBe('story_write');
    expect(result.user_payload.player_input).toBe('표를 살핍니다.');
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
