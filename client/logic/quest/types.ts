import type {
  DifficultyBadge as DifficultyBadgePayload,
  QuestPayload,
} from '@/services/wire.gen';

// Wire `tone` is a 5-literal subset (neutral/good/exp/accent/bad). Client Tone is
// a 9-literal union — 5 is a strict subset, so the assignment is safe. Expose
// wire type directly rather than a separate alias.
export type DifficultyBadge = DifficultyBadgePayload;
export type Quest = QuestPayload;
