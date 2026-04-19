import { Theme } from '@/constants/theme';
import type { Hero, Subject, SubjectKind, Quest, Place, LogEntry, PanelSlot } from '@/types/game';

const truncate = (s: string, n: number) =>
  s && s.length > n ? s.slice(0, n - 1) + '…' : s;

const SUBJECT_DOT: Record<SubjectKind, string> = {
  monster: Theme.bad,
  npc: Theme.textDim,
  merchant: Theme.accent,
};

export const INITIAL_HERO: Hero = {
  name: '리아넬',
  race: '엘프',
  class: '레인저',
  level: 7,
  exp: 1840, expMax: 2400,
  hp: 42, hpMax: 58,
  mp: 18, mpMax: 24,
  stats: { STR: 12, DEX: 17, CON: 13, INT: 14, WIS: 15, CHA: 10 },
  inventory: [
    { n: '엘븐 롱보우 +1', q: 1, eq: true },
    { n: '강철 단검', q: 1, eq: true },
    { n: '가죽 갑옷', q: 1, eq: true },
    { n: '치유 물약', q: 3, eq: false },
    { n: '은화', q: 47, eq: false },
    { n: '알 수 없는 편지', q: 1, eq: false },
  ],
  memos: [
    { t: '퀘스트', m: '바라드 숲의 실종자들을 찾아라' },
    { t: '단서', m: '"검은 돌" — 마을 장로가 언급' },
    { t: '의심', m: '여관 주인이 뭔가 숨기는 듯' },
  ],
  status: ['건강', '집중'],
  skills: ['정밀 사격', '추적', '야생 감각'],
  companions: ['카일 (성기사)', '모르간 (도적)'],
};

export const INITIAL_SUBJECT: Subject = {
  kind: 'monster',
  name: '그림자 고블린 두목',
  role: '몬스터',
  race: '고블린',
  level: 9,
  hp: 65, hpMax: 80,
  mood: '경계',
  trust: -55,
  known: ['키가 크다', '왼쪽 눈에 흉터', '썩은 이빨'],
};

export const INITIAL_QUEST: Quest = {
  title: '바라드 숲의 실종자',
  giver: '마을 장로',
  difficulty: { value: 3, max: 5, label: '중' },
  progress: { value: 2, max: 5 },
  goals: ['실종자 수색', '장로 증언 확보', '동굴 조사'],
  conditions: ['기한 없음', '생존 필수', '비밀 유지'],
  rewards: ['120골드', '경험치 +350', '장로의 신임'],
};

export const INITIAL_PLACE: Place = {
  name: '바라드 숲의 동굴',
  date: '1472년 10월 3일',
  hour: 18,
  weather: ['짙은 안개', '서늘함', '높은 습도'],
  features: ['석실', '출구 3곳', '바위 엄폐', '이끼빛 조명'],
  surroundings: ['고블린 진지', '낡은 제단실', '지하 수로', '붕괴된 회랑'],
};

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

const GM_TEMPLATES = [
  '횃불이 흔들리며, 당신의 그림자가 벽에 길게 늘어진다.',
  '두목이 으르렁거린다. "그 말을 믿으라고?"',
  '멀리서 쇠사슬이 끌리는 소리. 뭔가 다가오고 있다.',
  '돌바닥에 흩어진 피 자국. 아직 마르지 않았다.',
  '당신의 심장이 요동친다. 판단할 시간은 얼마 없다.',
  '두목이 한 걸음 물러서며 이빨을 드러냈다. "재미있군."',
  '공기가 차갑다. 동굴 깊은 곳에서 낮은 진동이 느껴진다.',
  '당신의 인장 반지가 희미하게 빛난다 — 마법의 흔적.',
];

export function fakeGMReply(_playerText: string): string {
  const pool = [...GM_TEMPLATES].sort(() => Math.random() - 0.5);
  const n = Math.random() < 0.4 ? 2 : 1;
  return pool.slice(0, n).join(' ');
}

export function rollD20(): number {
  return 1 + Math.floor(Math.random() * 20);
}

export function buildSubjectSlot(subject: Subject | null): PanelSlot {
  return {
    id: 'person',
    chip: subject
      ? { short: subject.role, label: truncate(subject.name, 10), dot: SUBJECT_DOT[subject.kind] }
      : { short: '인물', label: '없음', dot: Theme.textFaint },
    panel: subject ? {
      title: subject.name,
      meta: `Lv ${subject.level}`,
      barSplit: [
        { label: 'HP', value: subject.hp, max: subject.hpMax, color: Theme.hp, display: `${subject.hp}/${subject.hpMax}` },
        {
          label: '호감도',
          value: Math.abs(subject.trust),
          max: 100,
          color: subject.trust >= 0 ? Theme.accent : Theme.bad,
          display: subject.trust > 0 ? `+${subject.trust}` : `${subject.trust}`,
        },
      ],
      sections: [
        { label: '특징', text: '고블린 · 작은 체격 · 회녹색 피부 · 왼눈 흉터' },
        { label: '소지', text: '녹슨 단검 · 가죽 조끼 · 뼈 목걸이 · 낡은 주머니' },
        { label: '능력', nodes: [['STR','14'],['DEX','12'],['CON','13'],['INT','8'],['WIS','10'],['CHA','9']] as [string, string][] },
      ],
    } : null,
  };
}

export function buildQuestSlot(quest: Quest | null): PanelSlot {
  return {
    id: 'quest',
    chip: quest
      ? { short: '퀘스트', label: truncate(quest.title, 10), dot: Theme.accent }
      : { short: '퀘스트', label: '없음', dot: Theme.textFaint },
    panel: quest ? {
      title: quest.title,
      meta: quest.giver,
      barSplit: [
        { label: '난이도', value: quest.difficulty.value, max: quest.difficulty.max, color: Theme.bad, display: quest.difficulty.label },
        { label: '진행',   value: quest.progress.value,   max: quest.progress.max,   color: Theme.accent, display: `${quest.progress.value} / ${quest.progress.max}` },
      ],
      sections: [
        { label: '목표', text: quest.goals.join(' · ') },
        { label: '조건', text: quest.conditions.join(' · ') },
        { label: '보상', text: quest.rewards.join(' · ') },
      ],
    } : null,
  };
}

export function buildPlaceSlot(place: Place): PanelSlot {
  const periodOf = (h: number) =>
    h < 5 ? '새벽' : h < 12 ? '오전' : h < 17 ? '오후' : h < 20 ? '저녁' : '밤';
  return {
    id: 'bg',
    chip: { short: '장소', label: truncate(place.name, 10), dot: Theme.textDim },
    panel: {
      title: place.name,
      meta: place.date,
      bar: { label: '시간', value: place.hour, max: 24, color: Theme.accent, display: `${place.hour}시 · ${periodOf(place.hour)}` },
      sections: [
        { label: '날씨', text: place.weather.join(' · ') },
        { label: '특징', text: place.features.join(' · ') },
        { label: '주변', text: place.surroundings.join(' · ') },
      ],
    },
  };
}
