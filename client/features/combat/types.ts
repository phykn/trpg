export type CombatEnemy = {
  name: string;
  hp: number;
  hpMax: number;
  alive: boolean;
};

export type CombatBadge = {
  round: number;
  turnLabel: string;
  enemies: CombatEnemy[];
};
