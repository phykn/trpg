import type {
  Equipment as EquipmentPayload,
  EquipItem as EquipItemPayload,
  HeroPayload,
  InventoryItem as InventoryItemPayload,
  StatEntry,
} from '@/services/wire.gen';

export type Hero = HeroPayload;
export type EquipItem = EquipItemPayload;
export type Equipment = EquipmentPayload;
export type InventoryItem = InventoryItemPayload;
export type Stat = StatEntry;
export type Stats = StatEntry[];
