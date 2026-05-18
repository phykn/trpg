export type DecisionStateTone = 'neutral' | 'accent' | 'warning' | 'danger';

export type DecisionStateItem = {
  id: string;
  label: string;
  text: string;
  tone: DecisionStateTone;
  temporary?: boolean;
};
