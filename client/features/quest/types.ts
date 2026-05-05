import type { Tone } from '@/components/ui';

export type DifficultyBadge = { label: string; tone: Tone | null };

export type Quest = {
  id: string;
  title: string;
  giver: string;
  difficulty: DifficultyBadge;
  goals: string[];
  progressLabel: string;
  conditions: string[];
  rewards: { gold: number; exp: number };
  summary: string;
  status: 'pending' | 'active' | 'completed' | 'failed';
  actions: ('accept' | 'abandon')[];
};
