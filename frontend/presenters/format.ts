import type { InventoryItem } from '@/types/domain';

const SEP = ' · ';
const DASH = '—';

export function formatInventoryItem({ name, qty }: InventoryItem): string {
  return qty > 1 ? `${name} ×${qty}` : name;
}

export function joinList(items: string[]): string {
  return items.join(SEP);
}

export function joinOrDash(items: string[]): string {
  return items.length > 0 ? items.join(SEP) : DASH;
}

export function joinInventory(items: InventoryItem[]): string {
  return items.map(formatInventoryItem).join(SEP);
}

export function joinInventoryOrDash(items: InventoryItem[]): string {
  return items.length > 0 ? items.map(formatInventoryItem).join(SEP) : DASH;
}
