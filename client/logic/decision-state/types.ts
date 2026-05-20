export type DecisionStateTone = 'neutral' | 'accent' | 'warning' | 'danger' | 'level' | 'hp' | 'mp';

export type DecisionStateItem = {
  id: string;
  label: string;
  text: string;
  tone: DecisionStateTone;
  progress?: number;
  temporary?: boolean;
};
