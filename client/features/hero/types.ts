export type Stat = { label: string; value: number };
export type Stats = Stat[];

export type EquipItem = { name: string };

export type Equipment = {
  weapon: EquipItem | null;
  armor: EquipItem | null;
  accessory: EquipItem | null;
};

export type InventoryItem = { name: string; qty: number };

export type Hero = {
  name: string;
  alive: boolean;
  raceJob: string;
  gender: string;
  level: number;
  exp: number;
  expMax: number;
  canLevelUp: boolean;
  hp: number;
  hpMax: number;
  mp: number;
  mpMax: number;
  reviveCoins: number;
  reviveCoinsMax: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  status: string[];
  skills: string[];
  companions: string[];
};
