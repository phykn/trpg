function batchim(word: string): number | null {
  const c = word.charCodeAt(word.length - 1) - 0xac00;
  return c >= 0 && c <= 11171 ? c % 28 : null;
}
const eul = (w: string) => `${w}${batchim(w) ? '을' : '를'}`;
// ㄹ batchim (8) takes 로 like an open syllable.
const ro = (w: string) => { const b = batchim(w); return `${w}${b && b !== 8 ? '으로' : '로'}`; };

export const ko = {
  brand: '말과 주사위',
  loading: '불러오는 중입니다.',
  approaches: '능력치',
  raise: '올리기',
  lower: '내리기',
  traits: '특성',
  name: '이름',
  hero: '주인공',
  create: '시작하기',
  back: '뒤로',
  close: '닫기',
  chapterNo: (k: number) => `${k}장`,
  health: '체력',
  blocked: '이 판은 더 이어할 수 없습니다.',
  heroButton: (name: string, left: number, of: number) => `${name}, 체력 ${left}/${of}`,
  row: { goal: '목표', danger: '위험', ability: '능력', state: '상태', carried: '소지', here: '장소', around: '주변', record: '기록' },
  growth: '성장',
  // A scar stays for good, so it needs no end.
  tagLife: { scene: '이번 장면', chapter: '이번 장' } as Record<string, string>,
  promise: (name: string, what: string) => `${name}에게 ${what}`,
  kindness: (name: string) => `${name}에게 신세`,
  crisis: '위기',
  typing: '이야기를 쓰는 중',
  narrationFailed: '서술을 받지 못했습니다.',
  retryNarration: '다시 받기',
  command: '무엇을 할까요?',
  // Tapping a name starts the sentence; the player finishes it.
  draft: {
    go: (place: string) => `${ro(place)} 간다`,
    person: (name: string) => `${name}에게 `,
    thing: (name: string) => `${eul(name)} `,
  },
  send: '보내기',
  stuck: '응답을 받지 못했습니다.',
  resend: '다시 보내기',
  serverError: '서버 오류로 처리하지 못했습니다.',
  conflict: '게임 상태가 바뀌어 새로 불러왔습니다.',
  menu: '메뉴',
  closeMenu: '메뉴 닫기',
  toTitle: '처음으로',
  resume: '이어하기',
  prev: '이전 이야기',
  next: '다음 이야기',
  begin: '새로 시작',
  result: { success: '성공', fail: '실패', none: '', blocked: '막힘' } as Record<string, string>,
  highRisk: '되돌릴 수 없는 대가가 걸려 있습니다',
  hold: '주사위 굴리기',
  roll: '굴리기',
  skip: '건너뛰기',
  choose: '고른다',
  whereTo: '어디로 갈까요?',
  goTo: (place: string) => `${ro(place)} 갈까요?`,
  leave: '간다',
  thanks: '덕분에',
  because: '때문에',
} as const;
