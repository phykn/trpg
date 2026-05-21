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
        items: [
          { id: 'supply_token', name: '보급 표식', description: '바닥에 놓인 작은 표식입니다.' },
        ],
        targets: [
          {
            id: 'goblin_01',
            name: '쓰러진 고블린',
            kind: 'npc',
            alive: false,
            level: 1,
            raceJob: '고블린',
            gender: '',
            role: '쓰러진 적',
          },
          {
            id: 'wolf_01',
            name: '늑대',
            kind: 'npc',
            alive: true,
            raceJob: '야수',
            gender: '',
            role: '숲의 포식자',
          },
        ],
      },
      chapter: {
        id: 'chapter_01',
        title: '돌아갈 배는 없었다',
        summary: '흰섬의 첫 장입니다.',
        status: 'active',
      },
      scenarioCompleted: false,
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
        escapeReady: true,
        enemyPressure: 1,
        availableSupports: [
          {
            id: 'skill_shadow_thrust',
            kind: 'skill',
            name: '그림자 찌르기',
            tactic: 'precise',
            mpCost: 2,
            usable: true,
          },
        ],
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
        confirmLabel: '전투',
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
      log: [{ id: 1, kind: 'gm', text: '당신은 광장에 섭니다.', outcome: 'success' }],
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
    expect(state.log[0]).toEqual({ id: 1, kind: 'gm', text: '당신은 광장에 섭니다.', outcome: 'success' });
    expect(state.place?.surroundings[0].name).toBe('숲길');
    expect(state.place?.targets[0].name).toBe('쓰러진 고블린');
    expect(state.place?.targets[1].name).toBe('늑대');
    expect(state.quest).toBeNull();
    expect(state.chapter?.title).toBe('돌아갈 배는 없었다');
    expect(state.scenarioCompleted).toBe(false);
    expect(state.questOffers[0]?.title).toBe('첫 의뢰');
    expect(state.questOffers[0]?.actions).toEqual(['accept']);
    expect(state.combat?.round).toBe(2);
    expect(state.combat?.playerHearts.current).toBe(2);
    expect(state.combat?.enemyHearts.current).toBe(1);
    expect(state.combat?.lastRoll).toBe(16);
    expect(state.combat?.lastDc).toBe(12);
    expect(state.combat?.escapeReady).toBe(true);
    expect(state.combat?.enemyPressure).toBe(1);
    expect(state.combat?.availableSupports).toEqual([
      {
        id: 'skill_shadow_thrust',
        kind: 'skill',
        name: '그림자 찌르기',
        tactic: 'precise',
        mpCost: 2,
        usable: true,
      },
    ]);
    expect(state.combat?.enemies[0]).toMatchObject({
      id: 'wolf_01',
      name: '늑대',
      alive: true,
    });
    expect(state.pendingConfirmation?.confirmLabel).toBe('전투');
    expect(state.pendingRoll?.requiredRoll).toBe(13);
    expect(state.subject?.name).toBe('늑대');
    expect(state.subject?.alive).toBe(true);
    expect(state.subject?.role).toBe('숲의 포식자');
    expect(state.subject?.raceJob).toBe('야수');
    expect(state.subject?.level).toBe(1);
    expect(state.storyGraph.nodes.map((node) => node.id)).toEqual([
      'player_01',
      'town',
      'forest',
      'supply_token',
      'goblin_01',
      'wolf_01',
      'quest_01',
    ]);
  });
});
