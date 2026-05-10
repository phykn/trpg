export type EquipSlot = 'weapon' | 'armor' | 'accessory';

export type EquipItem = {
  id?: string;
  name: string;
};

export type Equipment = {
  weapon?: EquipItem | null;
  armor?: EquipItem | null;
  accessory?: EquipItem | null;
};

export type InventoryItem = {
  id?: string;
  name: string;
  qty: number;
  canUse?: boolean;
  equipSlots?: EquipSlot[];
};

export type Stat = {
  label: string;
  value: number;
};

export type Stats = Stat[];

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
  gold: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  status: string[];
  skills: string[];
  companions: string[];
};
