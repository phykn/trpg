// AUTO-GENERATED. Do not edit by hand. Run `npm run gen` from client/.

export type Code = string;
export type Message = string;
export type Value = number;
export type Max = number;
export type Label = string;
export type Kind = "stat" | "recruit";
export type Dc = number;
export type Stat = string;
export type StatLabel = string;
export type StatValue = number;
export type Mod = number;
export type RequiredRoll = number;
export type Target = string;
export type Reason = string;
export type Name = string;
export type Name1 = string;
export type Qty = number;
export type Label1 = string;
export type Value1 = number;
export type Name2 = string;
export type Alive = boolean;
export type Racejob = string;
export type Gender = string;
export type Level = number;
export type Exp = number;
export type Expmax = number;
export type Canlevelup = boolean;
export type Hp = number;
export type Hpmax = number;
export type Mp = number;
export type Mpmax = number;
export type Revivecoins = number;
export type Revivecoinsmax = number;
export type Gold = number;
export type Stats = StatEntry[];
export type Inventory = InventoryItem[];
export type Status = string[];
export type Skills = string[];
export type Companions = string[];

export interface Wire {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "ErrorPayload".
 */
export interface ErrorPayload {
  code: Code;
  message: Message;
  [k: string]: unknown;
}
/**
 * Difficulty tier display: numeric position (value/max) plus localized label.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "TierBadge".
 */
export interface TierBadge {
  value: Value;
  max: Max;
  label: Label;
  [k: string]: unknown;
}
/**
 * Wire shape for the `pending_check` SSE event and the `pendingCheck` slot
 * inside the `state` payload.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "PendingCheckPayload".
 */
export interface PendingCheckPayload {
  kind: Kind;
  dc: Dc;
  stat: Stat;
  stat_label: StatLabel;
  stat_value: StatValue;
  mod: Mod;
  required_roll: RequiredRoll;
  tier: TierBadge;
  target: Target;
  reason: Reason;
  [k: string]: unknown;
}
/**
 * Equipped item display — name only (qty implicit = 1).
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "EquipItem".
 */
export interface EquipItem {
  name: Name;
  [k: string]: unknown;
}
/**
 * Hero/subject equipment slots. Mirrors domain.Equipment field set.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "Equipment".
 */
export interface Equipment {
  weapon?: EquipItem | null;
  armor?: EquipItem | null;
  accessory?: EquipItem | null;
  [k: string]: unknown;
}
/**
 * Inventory row: item name + quantity.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "InventoryItem".
 */
export interface InventoryItem {
  name: Name1;
  qty: Qty;
  [k: string]: unknown;
}
/**
 * One row of the stats display: localized label + numeric value.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "StatEntry".
 */
export interface StatEntry {
  label: Label1;
  value: Value1;
  [k: string]: unknown;
}
/**
 * Wire shape for the `hero` slot inside the `state` payload.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "HeroPayload".
 */
export interface HeroPayload {
  name: Name2;
  alive: Alive;
  raceJob: Racejob;
  gender: Gender;
  level: Level;
  exp: Exp;
  expMax: Expmax;
  canLevelUp: Canlevelup;
  hp: Hp;
  hpMax: Hpmax;
  mp: Mp;
  mpMax: Mpmax;
  reviveCoins: Revivecoins;
  reviveCoinsMax: Revivecoinsmax;
  gold: Gold;
  stats: Stats;
  equipment: Equipment;
  inventory: Inventory;
  status: Status;
  skills: Skills;
  companions: Companions;
  [k: string]: unknown;
}
