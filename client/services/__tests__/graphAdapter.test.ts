import { adaptGraphState, deriveGraphSuggestions } from '../graphAdapter';

describe('adaptGraphState', () => {
  test('maps graph state into the existing display state shape', () => {
    const state = adaptGraphState({
      hero: {
        id: 'player_01',
        name: '테스터',
        level: 2,
        exp: 11,
        expMax: 30,
        canLevelUp: false,
        gold: 7,
        resources: {
          hp: { current: 18, maximum: 30, state: 'hurt' },
          mp: { current: 3, maximum: 10, state: 'strained' },
        },
        stats: {
          body: 3,
          agility: 2,
          mind: 1,
          presence: 0,
        },
        equipment: {
          weapon: { id: 'sword_01', name: '낡은 검' },
          armor: null,
          accessory: null,
        },
        inventory: [{ id: 'potion_01', name: '회복 물약', qty: 2, canUse: true, equipSlots: [] }],
        skills: ['기본 타격'],
        status: ['축복'],
      },
      place: {
        id: 'town',
        name: '광장',
        description: '작은 광장입니다.',
        exits: [
          { id: 'forest', name: '숲길', description: '나무가 빽빽합니다.' },
        ],
        targets: [
          {
            id: 'goblin_01',
            name: '쓰러진 고블린',
            kind: 'enemy',
            alive: false,
            level: 1,
            raceJob: '고블린',
            gender: '',
            role: '쓰러진 적',
            gold: 0,
            stats: { body: 1, mind: 1, agility: 1, presence: 1 },
            equipment: { weapon: null, armor: null, accessory: null },
            inventory: [],
            skills: [],
            status: ['쓰러짐'],
          },
          {
            id: 'wolf_01',
            name: '늑대',
            kind: 'enemy',
            alive: true,
            level: 3,
            raceJob: '야수',
            gender: '',
            role: '숲의 포식자',
            gold: 2,
            stats: {
              body: 3,
              agility: 4,
              mind: 1,
              presence: 2,
            },
            equipment: {
              weapon: { id: 'fang_01', name: '날카로운 송곳니' },
              armor: null,
              accessory: null,
            },
            inventory: [{ id: 'pelt_01', name: '늑대 가죽', qty: 1, canUse: false, equipSlots: [] }],
            skills: ['물어뜯기'],
            status: ['경계 중'],
          },
        ],
      },
      quest: null,
      questOffers: [
        {
          id: 'quest_01',
          title: '첫 의뢰',
          summary: '광장의 문제를 해결합니다.',
          giver: '늑대',
          difficulty: { label: '보통', tone: null },
          goals: ['늑대 쫓아내기'],
          progressLabel: '0/1',
          rewards: { gold: 5, exp: 10 },
          status: 'pending',
          actions: ['accept'],
        },
      ],
      combat: {
        round: 2,
        outcome: 'ongoing',
        playerHearts: { current: 2, maximum: 3 },
        enemyHearts: { current: 1, maximum: 3 },
        activeEnemyId: 'wolf_01',
        lastRoll: 16,
        lastDc: 12,
        participants: [
          {
            id: 'player_01',
            name: '테스터',
            side: 'player',
            hp: { current: 18, maximum: 30, state: 'hurt' },
            mp: { current: 3, maximum: 10, state: 'strained' },
          },
          {
            id: 'wolf_01',
            name: '늑대',
            side: 'enemy',
            hp: null,
            mp: null,
          },
        ],
      },
      pendingConfirmation: {
        id: 'confirm-1',
        kind: 'attack_start',
        title: '공격하시겠습니까?',
        body: '늑대를 공격해 전투를 시작합니다.',
        confirmLabel: '공격',
        cancelLabel: '취소',
        targetLabel: '늑대',
      },
      pendingRoll: {
        id: 'roll-1',
        kind: 'perceive',
        title: '정신 판정이 필요합니다',
        body: '자세히 살펴보려면 집중해야 합니다.',
        stat: 'mind',
        statLabel: '정신',
        requiredRoll: 13,
      },
      log: [{ id: 1, kind: 'gm', text: '당신은 광장에 섭니다.' }],
    });

    expect(state.hero.name).toBe('테스터');
    expect(state.hero.hp).toBe(18);
    expect(state.hero.hpMax).toBe(30);
    expect(state.hero.mp).toBe(3);
    expect(state.hero.mpMax).toBe(10);
    expect(state.hero.level).toBe(2);
    expect(state.hero.exp).toBe(11);
    expect(state.hero.expMax).toBe(30);
    expect(state.hero.canLevelUp).toBe(false);
    expect(state.hero.gold).toBe(7);
    expect(state.hero.equipment.weapon).toEqual({ id: 'sword_01', name: '낡은 검' });
    expect(state.hero.inventory).toEqual([{ id: 'potion_01', name: '회복 물약', qty: 2, canUse: true, equipSlots: [] }]);
    expect(state.hero.skills).toEqual(['기본 타격']);
    expect(state.hero.status).toEqual(['축복']);
    expect(state.hero.stats).toEqual([
      { label: '근력', value: 3 },
      { label: '지력', value: 1 },
      { label: '민첩', value: 2 },
      { label: '매력', value: 0 },
    ]);
    expect(state.place?.name).toBe('광장');
    expect(state.place?.surroundings[0].name).toBe('숲길');
    expect(state.place?.targets[0].name).toBe('쓰러진 고블린');
    expect(state.place?.targets[1].name).toBe('늑대');
    expect(state.quest).toBeNull();
    expect(state.questOffers[0]?.title).toBe('첫 의뢰');
    expect(state.questOffers[0]?.actions).toEqual(['accept']);
    expect(state.combat?.round).toBe(2);
    expect(state.combat?.playerHearts.current).toBe(2);
    expect(state.combat?.enemyHearts.current).toBe(1);
    expect(state.combat?.lastRoll).toBe(16);
    expect(state.combat?.lastDc).toBe(12);
    expect(state.combat?.enemies[0]).toMatchObject({
      id: 'wolf_01',
      name: '늑대',
      alive: true,
    });
    expect(state.pendingConfirmation?.confirmLabel).toBe('공격');
    expect(state.pendingRoll?.requiredRoll).toBe(13);
    expect(state.subject?.name).toBe('늑대');
    expect(state.subject?.alive).toBe(true);
    expect(state.subject?.role).toBe('숲의 포식자');
    expect(state.subject?.raceJob).toBe('야수');
    expect(state.subject?.gold).toBe(2);
    expect(state.subject?.equipment.weapon).toEqual({ id: 'fang_01', name: '날카로운 송곳니' });
    expect(state.subject?.inventory).toEqual([{ id: 'pelt_01', name: '늑대 가죽', qty: 1, canUse: false, equipSlots: [] }]);
    expect(state.subject?.skills).toEqual(['물어뜯기']);
    expect(state.subject?.known).toEqual(['경계 중']);
    expect(state.subject?.stats).toEqual([
      { label: '근력', value: 3 },
      { label: '지력', value: 1 },
      { label: '민첩', value: 4 },
      { label: '매력', value: 2 },
    ]);
    expect(state.storyGraph.nodes.map((node) => node.id)).toEqual([
      'player_01',
      'town',
      'forest',
      'goblin_01',
      'wolf_01',
      'quest_01',
    ]);
  });

  test('derives graph suggestions from visible targets and exits', () => {
    const suggestions = deriveGraphSuggestions({
      hero: {
        id: 'player_01',
        name: '테스터',
        level: 1,
        exp: 0,
        expMax: 20,
        canLevelUp: false,
        gold: 0,
        resources: {
          hp: { current: 20, maximum: 20, state: 'healthy' },
          mp: { current: 10, maximum: 10, state: 'ready' },
        },
        stats: {},
        equipment: { weapon: null, armor: null, accessory: null },
        inventory: [],
        skills: [],
        status: [],
      },
      place: {
        id: 'town',
        name: '광장',
        description: '',
        exits: [{ id: 'watch', name: '망루', description: '' }],
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
          {
            id: 'wolf_01',
            name: '늑대',
            kind: 'enemy',
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
      },
      quest: null,
      questOffers: [],
      combat: null,
      pendingConfirmation: null,
      pendingRoll: null,
      log: [{ id: 1, kind: 'gm', text: '당신은 광장에 있습니다.' }],
    });

    expect(suggestions).toEqual([
      { label: '늑대를 공격합니다', inputText: '늑대를 공격합니다' },
      { label: '에드릭에게 말을 겁니다', inputText: '에드릭에게 말을 겁니다' },
      { label: '망루로 이동합니다', inputText: '망루로 이동합니다' },
    ]);
  });
});
