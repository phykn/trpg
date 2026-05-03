import type { Tone } from '@/components/ui';

export type DifficultyBadge = { label: string; tone: Tone | null };

export type Quest = {
  title: string;
  giver: string;
  difficulty: DifficultyBadge;
  goals: string[];
  progressLabel: string;
  conditions: string[];
  rewards: { gold: number; exp: number };
  summary: string;
};
