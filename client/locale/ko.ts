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
    language: 'LANGUAGE',
  },
  ability: {
    body: '근력',
    agility: '민첩',
    mind: '지력',
    presence: '매력',
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
    talk: '대화',
    inspect: '살펴보기',
    pickup: '줍기',
  },
  table: {
    map: '지도',
    notes: '노트',
    sheet: '시트',
    noNotes: '기록된 노트가 없습니다',
  },
  legend: {
    place: '장소',
    character: '캐릭터',
    item: '물품',
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
    normalRisk: '보통',
  },
  roll: {
    check: '판정',
    difficulty: '난이도',
    required: '필요 주사위',
    orMore: '이상',
    abilityBonus: '능력',
    affinity: '친밀도',
    liking: '호감',
    stopLabel: '주사위 굴림 중단',
    rollLabel: '주사위 굴리기',
    halt: '정지',
    success: '성공',
    fail: '실패',
    exceed: '초과',
    short: '부족',
    die: '주사위',
  },
  cue: {
    groupLabel: '장면 변화',
  },
  decision: {
    title: '현재 판단 기준',
    place: '장소',
    goal: '목표',
    risk: '위험',
    status: '상태',
    temporary: '이번 선택',
  },
  composer: {
    placeholderLocked: '판정을 먼저 굴려주세요',
    placeholder: '당신은 무엇을 합니까?',
    send: '전송',
    sendAction: '행동 보내기',
    stopAction: '행동 중단',
  },
  empty: {
    panel: '비어 있음',
    suggestionHint: '아래 입력창에 자유롭게 적어보세요',
  },
  level: {
    title: '레벨업',
    cancel: '취소',
    permanent: '영구 적용',
    confirmAction: '레벨업 확정',
    cancelAction: '레벨업 취소',
    maxHpChoice: '최대 HP +1',
    maxMpChoice: '최대 MP +1',
    loadingChoices: '성장 선택지를 준비 중입니다',
    raiseSuffix: '올리기',
  },
  gameOver: {
    ending: '이야기는 여기서 끝납니다.',
    restart: '새 이야기 시작',
    restartAction: '새 이야기 시작',
  },
  quest: {
    accept: '수락',
    abandon: '포기',
    abandonTitle: '퀘스트 포기',
    abandonBlurb: '진행 상황이 사라집니다.',
    name: '퀘스트',
    offer: '제안',
  },
  hero: {
    chip: '주인공',
    ability: '능력',
    equip: '장비',
    inventory: '소지',
    skill: '기술',
    companion: '동료',
    hp: '체력',
    mp: '마나',
    exp: '경험',
    revive: '소생',
    gold: '소지금',
    goldCoin: '금화',
  },
  combat: {
    label: '전투',
    attack: '공격',
    precise: '정밀',
    guarded: '방어',
    reckless: '무모',
    createDistance: '거리',
    escape: '이탈',
    talk: '대화',
    pressure: '압박',
    defend: '방어',
    skill: '기술',
    skillFallback: '기술을 사용합니다',
    flee: '도주',
    persuade: '설득',
    playerHearts: '내 하트',
    enemyHearts: '적 하트',
    player: '당신',
  },
  menu: {
    newGame: '새로운 이야기',
    soundOff: '소리 끄기',
    soundOn: '소리 켜기',
    menuLabel: '메뉴',
  },
  subject: {
    chip: 'NPC',
  },
  confirm: {
    ok: '확인',
  },
  error: {
    heading: '오류',
    retry: '다시 시도',
    unknown: '알 수 없는 오류',
    invalidStat: '잘못된 능력치입니다.',
  },
  shell: {
    loading: [
      '세계 펼치는 중',
      '모닥불 지피는 중',
      '지도에 잉크 묻히는 중',
      '별빛 살피는 중',
      '이야기의 첫 줄 적는 중',
    ] as readonly string[],
  },
  newGame: {
    defaultName: '주인공',
    noProfiles: '선택 가능한 시나리오가 없습니다.',
    hint: '이름을 정하고, 세계와 종족을 고르면 시작합니다.',
    creating: '생성 중…',
    namePlaceholder: '등장인물의 이름',
    male: '남성',
    female: '여성',
    noRaces: '선택 가능한 종족이 없습니다.',
    korean: '한국어',
    english: 'English',
    leaveBlurb: '진행 중인 이야기를 멈춥니다. 새로운 이야기를 시작합니다.',
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
  talkTo: (name: string) => `${name}에게 말을 겁니다`,
  pickUp: (name: string) => `${name}${josaObject(name)} 줍습니다`,
  inspect: (name: string) => `${name}${josaObject(name)} 살펴봅니다`,
  attack: (name: string) => `${name}${josaObject(name)} 공격합니다`,
  persuade: (name: string) => `${name}${josaObject(name)} 설득합니다`,
  inspectSurroundings: () => '주변을 살펴봅니다',
  defend: () => '방어합니다',
  flee: () => '도망칩니다',
  createDistance: () => '거리를 벌립니다',
  escape: () => '빠져나갑니다',
  guarded: () => '방어적으로 움직입니다',
  preciseAttack: (name: string) => `${name}${josaObject(name)} 정밀하게 공격합니다`,
  recklessAttack: (name: string) => `${name}${josaObject(name)} 거세게 몰아붙입니다`,
  useSkill: (name: string) => `${name}${josaObject(name)} 사용합니다`,
  useItem: (name: string) => `${name} 사용`,
  equipItem: (name: string) => `${name} 장비`,
  unequipItem: (name: string) => `${name} 해제`,
  deceased: (name: string) => `${name} (죽음)`,
  here: (label: string) => `현재 ${label}`,
  currentLocation: (label: string) => `현재 위치 · ${label}`,
  neighborhoodMap: (label: string) => `${label} 주변 지도`,
  placeCount: (n: number) => `장소 ${n}곳`,
  reachableCount: (n: number) => `이동 가능 ${n}`,
  affinity: (delta: number) => `호감도 ${delta > 0 ? '+' : ''}${delta}`,
  nearbySummary: (people: number, places: number, tasks: number, items = 0) => {
    const parts = [`인물 ${people}`, `장소 ${places}`];
    if (items > 0) parts.push(`물품 ${items}`);
    parts.push(`할 일 ${tasks}`);
    return parts.join(' · ');
  },
  combatWith: (name: string) => `${name}${josaWith(name)} 전투 중`,
  combatExchange: (round: number) => `${round}번째 교환`,
};

function josaObject(value: string): '을' | '를' {
  const last = value.charCodeAt(value.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return '를';
  return (last - 0xac00) % 28 === 0 ? '를' : '을';
}

function josaWith(value: string): '과' | '와' {
  const last = value.charCodeAt(value.length - 1);
  if (last < 0xac00 || last > 0xd7a3) return '와';
  return (last - 0xac00) % 28 === 0 ? '와' : '과';
}
