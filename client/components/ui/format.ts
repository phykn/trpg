import type { InventoryItem } from '@/features/hero';

export const SEP = ' · ';
export const DASH = '—';

export function formatInventoryItem({ name, qty }: InventoryItem): string {
  return qty > 1 ? `${name} ×${qty}` : name;
}

export function joinOrDash(items: string[]): string {
  return items.length > 0 ? items.join(SEP) : DASH;
}

export function characterMeta(level: number, raceJob: string, gender: string): string {
  const parts = [`Lv ${level}`, raceJob];
  if (gender) parts.push(gender);
  return parts.join(SEP);
}

export function withDeath(name: string, alive: boolean | undefined): string {
  return alive === false ? `${name} (죽음)` : name;
}
