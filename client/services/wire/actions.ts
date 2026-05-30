export type QuestAction = {
  kind: 'accept' | 'abandon';
  quest_id: string;
};

export type ConfirmRequest = {
  confirmation_id: string;
  decision: 'confirm' | 'cancel';
};

export type GraphRollRequest = {
  roll_id: string;
};

type CombatSupportCommandFields = {
  support_id?: string;
  support_kind?: 'skill';
};

export type CombatCommand =
  | ({ command: 'attack'; target: string } & CombatSupportCommandFields)
  | ({ command: 'talk'; target: string } & CombatSupportCommandFields)
  | ({ command: 'defend' } & CombatSupportCommandFields)
  | ({ command: 'flee' } & CombatSupportCommandFields);

export type GraphAction = {
  verb:
    | 'move'
    | 'transfer'
    | 'use'
    | 'attack'
    | 'speak'
    | 'perceive'
    | 'decide'
    | 'rest'
    | 'pass';
  what?: string | string[] | null;
  from?: string | null;
  to?: string | null;
  with?: string | null;
  how?: string | null;
  note?: string | null;
};
