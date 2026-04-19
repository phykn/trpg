import type { Hero, Subject, Quest, Place } from '@/types/domain';
import type { LogEntry } from '@/types/ui';
import type { Check } from '@/services';

export const INITIAL_HERO: Hero = {
  name: '리아넬',
  race: '엘프',
  class: '레인저',
  level: 7,
  exp: 1840, expMax: 2400,
  hp: 42, hpMax: 58,
  mp: 18, mpMax: 24,
  stats: { STR: 12, DEX: 17, CON: 13, INT: 14, WIS: 15, CHA: 10 },
  equipment: {
    head: { name: '숲지기의 두건' },
    top: { name: '정령 수호 가죽 갑옷' },
    bottom: { name: '사슴가죽 바지' },
    feet: { name: '이끼 걸음 부츠' },
    leftHand: { name: '은제 의식용 단검' },
    rightHand: { name: '엘븐 롱보우 +1' },
    acc1: { name: '별빛 인장 반지' },
    acc2: { name: '바람결 펜던트' },
  },
  inventory: [
    { name: '치유 물약', qty: 3 },
    { name: '마나 정수', qty: 2 },
    { name: '은화', qty: 47 },
    { name: '알 수 없는 봉인 편지', qty: 1 },
    { name: '말린 약초 다발', qty: 5 },
    { name: '엘프 여행식량', qty: 8 },
  ],
  status: ['건강', '집중', '은신 중', '추적 감지 활성'],
  skills: ['정밀 사격', '추적', '야생 감각', '이중 사격', '그림자 이동', '자연과의 교감'],
  companions: ['카일 (인간 성기사)', '모르간 (하플링 도적)', '실바 (드루이드 견습생)'],
};

export const INITIAL_SUBJECT: Subject = {
  name: '그림자 고블린 두목',
  role: '몬스터',
  race: '고블린',
  class: '도적',
  level: 9,
  hp: 65, hpMax: 80,
  trust: -55,
  known: ['작은 체격', '회녹색 피부', '왼눈 흉터', '썩은 이빨', '쉰 목소리', '지휘관 문신', '부러진 송곳니'],
  stats: { STR: 14, DEX: 12, CON: 13, INT: 8, WIS: 10, CHA: 9 },
  inventory: [
    { name: '녹슨 단검', qty: 1 },
    { name: '가죽 조끼', qty: 1 },
    { name: '뼈 목걸이', qty: 1 },
    { name: '낡은 주머니', qty: 1 },
    { name: '고블린 문양 깃발', qty: 1 },
    { name: '훔친 은화 주머니', qty: 2 },
  ],
};

export const INITIAL_QUEST: Quest = {
  title: '바라드 숲의 실종자',
  giver: '마을 장로',
  difficulty: { value: 3, max: 7, label: '보통' },
  goals: ['실종자 네 명 수색', '장로의 증언 확보', '동굴 내부 조사', '고블린 진지 규모 확인'],
  conditions: ['기한 없음', '생존 필수', '비밀 유지', '민간인 피해 최소화'],
  rewards: { gold: 120, exp: 350 },
  memo: '장로의 신임을 얻으면 마을 봉인 해제에 도움이 될 수 있음. 다만 서쪽 교역로 상인 길드가 이 수색을 탐탁지 않게 여긴다는 소문이 있으므로 신중히 움직일 것.',
};

export const INITIAL_PLACE: Place = {
  name: '바라드 숲의 동굴',
  date: '1472년 10월 3일',
  hour: 18,
  weather: ['짙은 안개', '서늘함', '높은 습도', '간헐적 이슬비'],
  features: ['석실 구조', '출구 3곳', '바위 엄폐물', '이끼빛 조명', '얕은 지하수 웅덩이', '천장의 균열'],
  surroundings: ['고블린 진지', '낡은 제단실', '지하 수로', '붕괴된 회랑', '박쥐 서식지', '버려진 광부 캠프'],
};

export const PENDING_CHECK: Check = { stat: 'DEX', dc: 12, mod: 3 };

export const INITIAL_LOG: LogEntry[] = [
  { id: 1, kind: 'gm',    text: '축축한 동굴 안, 횃불 그림자가 벽을 따라 춤춘다.' },
  { id: 2, kind: 'gm',    text: '그림자 고블린 두목이 당신을 노려본다. "인간…아니, 엘프인가. 여긴 네가 올 곳이 아냐."' },
  { id: 3, kind: 'act',   text: '리아넬이 활을 겨눈다.' },
  { id: 4, kind: 'roll',  check: 'DEX', dc: 12, roll: 14, mod: 3, result: 'success' },
  { id: 5, kind: 'gm',    text: '당신은 바위 뒤로 소리 없이 미끄러졌다. 두목은 아직 당신을 보지 못했다.' },
  { id: 6, kind: 'player',text: '그에게 협상을 시도한다.' },
  { id: 7, kind: 'roll',  check: 'CHA', dc: 12, roll: 6,  mod: 0, result: 'fail' },
  { id: 8, kind: 'gm',    text: '"흥. 말로 속이려 드는구나." 두목의 손이 단검 자루로 향한다.' },
];
