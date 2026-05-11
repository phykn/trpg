import type { InventoryItem } from '@/logic/hero';
import { compose, ko } from '@/locale/ko';

export const SEP = ' · ';
export const DASH = '—';

export function formatInventoryItem({ name, qty }: InventoryItem): string {
  return qty > 1 ? `${name} ×${qty}` : name;
}

export function formatGold(gold: number): string {
  return `${ko.hero.goldCoin}(${gold})`;
}

export function joinOrDash(items: string[]): string {
  return items.length > 0 ? items.join(SEP) : DASH;
}

export function signed(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

export function characterMeta(level: number, raceJob: string, gender: string): string {
  const parts = [`Lv ${level}`, raceJob, gender].filter((part) => part.trim().length > 0);
  return parts.join(SEP);
}

export function withDeath(name: string, alive: boolean | undefined): string {
  return alive === false ? compose.deceased(name) : name;
}
