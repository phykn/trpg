import type { SubjectPayload } from '@/services/wire.gen';

// Subject은 hp/hpMax만 노출. mp/mpMax는 의도적으로 미공개 — subject panel은
// 호감도/직업/장비 위주이고, NPC의 마력 게이지는 player가 알 정보 아님.
// (이 invariant는 서버 wire 모델 SubjectPayload에서도 지켜집니다 — mp 필드 부재.)
export type Subject = SubjectPayload;
