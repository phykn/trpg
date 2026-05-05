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
export type Name3 = string;
export type Alive1 = boolean;
export type Role = string;
export type Racejob1 = string;
export type Gender1 = string;
export type Trust = number;
export type Known = string[];
export type Level1 = number;
export type Hp1 = number;
export type Hpmax1 = number;
export type Stats1 = StatEntry[];
export type Inventory1 = InventoryItem[];
export type Skills1 = string[];
export type Label2 = string;
export type Tone = ("neutral" | "good" | "exp" | "accent" | "bad") | null;
export type Gold1 = number;
export type Exp1 = number;
export type Id = string;
export type Title = string;
export type Summary = string;
export type Giver = string;
export type Goals = string[];
export type Progresslabel = string;
export type Conditions = string[];
export type Status1 = "pending" | "active" | "completed" | "failed";
export type Actions = ("accept" | "abandon")[];

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
/**
 * Wire shape for the `subject` slot inside the `state` payload.
 * Field order matches mapping/to_front.to_subject's dict insertion order.
 * NPC mp/mpMax is intentionally absent — subject panel doesn't expose
 * NPC mana to the player.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "SubjectPayload".
 */
export interface SubjectPayload {
  name: Name3;
  alive: Alive1;
  role: Role;
  raceJob: Racejob1;
  gender: Gender1;
  trust: Trust;
  known: Known;
  level: Level1;
  hp: Hp1;
  hpMax: Hpmax1;
  stats: Stats1;
  equipment: Equipment;
  inventory: Inventory1;
  skills: Skills1;
  [k: string]: unknown;
}
/**
 * Difficulty visual atom for the quest panel: localized label + tone hint
 * (the latter aligns with client `Tone` design-system literals; the 5-value
 * subset matches mapping.labels._TIER_TONE).
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "DifficultyBadge".
 */
export interface DifficultyBadge {
  label: Label2;
  tone?: Tone;
  [k: string]: unknown;
}
/**
 * Wire view of quest rewards — gold + exp only. Domain QuestRewards also
 * carries `items: list[str]` but the quest panel doesn't surface them today.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "QuestRewards".
 */
export interface QuestRewards {
  gold: Gold1;
  exp: Exp1;
  [k: string]: unknown;
}
/**
 * Wire shape for the `quest` slot inside the `state` payload.
 * Field order matches mapping/to_front.to_quest's dict insertion order.
 * `status` / `actions` are narrowed to the four/two literals to_quest can
 * emit — domain Quest.status carries `locked`/`abandoned` too but those
 * never reach the active-quest path.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "QuestPayload".
 */
export interface QuestPayload {
  id: Id;
  title: Title;
  summary: Summary;
  giver: Giver;
  difficulty: DifficultyBadge;
  goals: Goals;
  progressLabel: Progresslabel;
  conditions: Conditions;
  rewards: QuestRewards;
  status: Status1;
  actions: Actions;
  [k: string]: unknown;
}
