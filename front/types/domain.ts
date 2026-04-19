export type Stats = {
  STR: number;
  DEX: number;
  CON: number;
  INT: number;
  WIS: number;
  CHA: number;
};

export type StatKey = keyof Stats;

export type InventoryItem = {
  name: string;
  qty: number;
};

export type EquipItem = {
  name: string;
};

export type Equipment = {
  head: EquipItem | null;
  top: EquipItem | null;
  bottom: EquipItem | null;
  feet: EquipItem | null;
  leftHand: EquipItem | null;
  rightHand: EquipItem | null;
  acc1: EquipItem | null;
  acc2: EquipItem | null;
};

export type Hero = {
  name: string;
  race: string;
  class: string;
  level: number;
  exp: number;
  expMax: number;
  hp: number;
  hpMax: number;
  mp: number;
  mpMax: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  status: string[];
  skills: string[];
  companions: string[];
};

export type Subject = {
  name: string;
  role: string;
  race: string;
  class: string;
  trust: number;
  known: string[];
  level: number;
  hp: number;
  hpMax: number;
  stats: Stats;
  inventory: InventoryItem[];
};

export type Quest = {
  title: string;
  giver: string;
  difficulty: { value: number; max: number; label: string };
  goals: string[];
  conditions: string[];
  rewards: { gold: number; exp: number };
  memo: string;
};

export type Place = {
  name: string;
  date: string;
  hour: number;
  weather: string[];
  features: string[];
  surroundings: string[];
};

export type RollResult = 'success' | 'fail';
