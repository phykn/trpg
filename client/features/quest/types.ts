import type {
  DifficultyBadge as DifficultyBadgePayload,
  QuestPayload,
} from '@/services/wire.gen';

// Wire `tone`은 5-literal subset (neutral/good/exp/accent/bad). 클라 Tone은
// 9-literal union — 5-literal은 진부분집합이라 안전. 별도 alias로 export하지
// 않고 직접 wire 타입을 노출.
export type DifficultyBadge = DifficultyBadgePayload;
export type Quest = QuestPayload;
