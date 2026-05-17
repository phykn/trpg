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
  tactic: 'precise' | 'guarded' | 'reckless' | 'create_distance' | 'talk';
  mpCost: number;
  usable: boolean;
};

export type CombatBadge = {
  round: number;
  outcome: 'ongoing' | 'victory' | 'defeat' | 'fled' | 'escaped' | 'surrendered' | 'combat_stopped';
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
