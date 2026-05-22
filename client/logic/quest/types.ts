export type DifficultyBadge = {
  label: string;
  tone?: 'neutral' | 'good' | 'exp' | 'accent' | 'bad' | null;
};

export type Quest = {
  id: string;
  title: string;
  summary: string;
  giver: string;
  difficulty: DifficultyBadge;
  goals: string[];
  progressLabel: string;
  rewards: { gold: number; exp: number };
  status: 'pending' | 'active' | 'completed' | 'failed';
  actions: ('accept' | 'abandon')[];
  choices: { id: string; label: string }[];
};
