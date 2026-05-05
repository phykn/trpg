import type { Equipment, InventoryItem, Stats } from '@/features/hero';

// Subject은 hp/hpMax만 노출. mp/mpMax는 의도적으로 미공개 — subject panel은
// 호감도/직업/장비 위주이고, NPC의 마력 게이지는 player가 알 정보 아님.
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
