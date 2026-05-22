export type CombatHeart = {
  current: number;
  maximum: number;
};

export type CombatEnemy = {
  id?: string;
  name: string;
  alive: boolean;
};

export type CombatSupport = {
  id: string;
  kind: 'skill';
  name: string;
  action: 'attack' | 'defend' | 'flee' | 'talk';
  mpCost: number;
  usable: boolean;
};

export type CombatBadge = {
  round: number;
  outcome: 'ongoing' | 'victory' | 'defeat' | 'escaped' | 'combat_stopped';
  turnLabel: string;
  playerHearts: CombatHeart;
  enemyHearts: CombatHeart;
  enemies: CombatEnemy[];
  availableSupports: CombatSupport[];
  escapeReady: boolean;
  enemyPressure: number;
  lastRoll?: number | null;
  lastDc?: number | null;
};
