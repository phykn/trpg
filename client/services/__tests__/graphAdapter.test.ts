import { adaptGraphState } from '../graphAdapter';

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
            id: 'wolf_01',
            name: '늑대',
            hp: { current: 5, maximum: 12, state: 'hurt' },
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
            hp: { current: 5, maximum: 12, state: 'hurt' },
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
      { label: '몸', value: 3 },
      { label: '민첩', value: 2 },
      { label: '정신', value: 1 },
      { label: '존재감', value: 0 },
    ]);
    expect(state.place?.name).toBe('광장');
    expect(state.place?.surroundings[0].name).toBe('숲길');
    expect(state.place?.targets[0].name).toBe('늑대');
    expect(state.quest).toBeNull();
    expect(state.questOffers[0]?.title).toBe('첫 의뢰');
    expect(state.questOffers[0]?.actions).toEqual(['accept']);
    expect(state.combat?.round).toBe(2);
    expect(state.combat?.enemies[0]).toMatchObject({
      id: 'wolf_01',
      name: '늑대',
      hp: 5,
      hpMax: 12,
      alive: true,
    });
    expect(state.pendingConfirmation?.confirmLabel).toBe('공격');
    expect(state.pendingCheck).toBeNull();
    expect(state.subject).toBeNull();
    expect(state.storyGraph.nodes.map((node) => node.id)).toEqual([
      'player_01',
      'town',
      'forest',
      'wolf_01',
      'quest_01',
    ]);
  });
});
