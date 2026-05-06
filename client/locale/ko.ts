export const ko = {
  action: {
    start: '시작',
    roll: '굴리기',
    stop: '멈추기',
    fast: '빠르게',
    accurate: '정확하게',
  },
  form: {
    name: 'NAME',
    gender: 'GENDER',
    world: 'WORLD',
    race: 'RACE',
  },
  ability: {
    STR: '근력',
    DEX: '민첩',
    CON: '건강',
    INT: '지능',
    WIS: '지혜',
    CHA: '매력',
  },
  panel: {
    environment: '환경',
    appearance: '모습',
    description: '설명',
    role: '역할',
    traits: '특징',
    affinity: '호감도',
    commission: '의뢰',
    goal: '목표',
    summary: '요약',
    condition: '조건',
    reward: '보상',
    map: '지도',
    neighborhood: '주변',
    storyGraph: '현재 스토리 그래프',
    here: '현재 위치',
    miniMap: '미니맵',
    fullMap: '전체 지도',
    mapReset: '맵 다시 맞추기',
    mapLoading: '지도를 펼칩니다.',
    noGame: '진행 중인 게임이 없습니다.',
    mapError: '지도를 펼치지 못했습니다.',
    noStoryData: '스토리 데이터 없음',
    move: '이동',
    approach: '접근',
  },
  legend: {
    place: '장소',
    character: '캐릭터',
    quest: '퀘스트',
    currentLocation: '현재 위치',
    reachable: '갈 수 있는 곳',
    unreachable: '갈 수 없는 곳',
  },
  status: {
    facing: '대면 중',
    moveBlocked: '이동 불가',
    approachBlocked: '접근 불가',
    busy: '처리 중',
  },
} as const;

export const compose = {
  moveTo: (name: string) => {
    const last = name.charCodeAt(name.length - 1);
    if (last < 0xac00 || last > 0xd7a3) return `${name}(으)로 이동합니다`;
    const final = (last - 0xac00) % 28;
    if (final === 0 || final === 8) return `${name}로 이동합니다`;
    return `${name}으로 이동합니다`;
  },
  approachTo: (name: string) => `${name}에게 접근합니다`,
  deceased: (name: string) => `${name} (죽음)`,
  here: (label: string) => `현재 ${label}`,
  placeCount: (n: number) => `장소 ${n}곳`,
  reachableCount: (n: number) => `이동 가능 ${n}`,
};
