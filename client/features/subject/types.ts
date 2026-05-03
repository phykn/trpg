import type { Equipment, InventoryItem, Stats } from '@/features/hero';

export type Subject = {
  name: string;
  alive: boolean;
  raceJob: string;
  gender: string;
  role: string;
  trust: number;
  known: string[];
  level: number;
  hp: number;
  hpMax: number;
  stats: Stats;
  equipment: Equipment;
  inventory: InventoryItem[];
  skills: string[];
};
