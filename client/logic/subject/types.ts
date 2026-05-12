import type { Equipment, InventoryItem, Stat } from '@/logic/hero/types';

export type Subject = {
  name: string;
  alive: boolean;
  role: string;
  raceJob: string;
  gender: string;
  trust: number;
  known: string[];
  level: number;
  gold?: number;
  stats: Stat[];
  equipment: Equipment;
  inventory: InventoryItem[];
  skills: string[];
};
