import type { Equipment, InventoryItem, Stat } from '@/logic/hero/types';

// Only hp/hpMax is exposed for subjects. mp/mpMax is intentionally absent —
// the subject panel focuses on affinity/role/equipment.
export type Subject = {
  name: string;
  alive: boolean;
  role: string;
  raceJob: string;
  gender: string;
  trust: number;
  known: string[];
  level: number;
  hp: number;
  hpMax: number;
  gold?: number;
  stats: Stat[];
  equipment: Equipment;
  inventory: InventoryItem[];
  skills: string[];
};
