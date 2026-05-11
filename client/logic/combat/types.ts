export type CombatHeart = {
  current: number;
  maximum: number;
};

export type CombatEnemy = {
  id?: string;
  name: string;
  alive: boolean;
};

export type CombatBadge = {
  round: number;
  turnLabel: string;
  playerHearts: CombatHeart;
  enemyHearts: CombatHeart;
  enemies: CombatEnemy[];
};
