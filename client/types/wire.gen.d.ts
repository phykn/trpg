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
export type Name4 = string;
export type Blurb = string;
export type Difficulty = string | null;
export type Label3 = string;
export type Tone1 = "good" | "neutral" | "bad";
export type Name5 = string;
export type Level2 = number;
export type Racejob2 = string;
export type Gender2 = string;
export type Blurb1 = string;
export type Trust1 = number;
export type Name6 = string;
export type Description = string;
export type Dayphase = string;
export type Weather = string[];
export type Features = string[];
export type Surroundings = PlaceSurrounding[];
export type Targets = PlaceTarget[];
export type JudgeKind = "pending_check_trigger";
export type Tier = "very_easy" | "easy" | "normal" | "hard" | "very_hard" | "legend" | "myth";
export type Stat1 = "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA";
export type Targets1 = string[];
export type Reason1 = string;
export type JudgeKind1 = "refuse";
export type Category = "out_of_game" | "meta_breaking";
export type MessageHint = string;
export type JudgeKind2 = "verb";
export type Name7 = "move" | "transfer" | "use" | "attack" | "cast" | "speak" | "alter" | "perceive" | "rest" | "wait";
/**
 * @maxItems 8
 */
export type TargetIds =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string];
export type JudgeKind3 = "verbs";
export type Actions1 = Verb[];
/**
 * SSE `judge` event payload — discriminated union over `judge_kind`.
 * RootModel is the Pydantic v2 way to wrap a non-class root type so it can
 * be exported alongside other top-level wire models in wire/export.py.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "JudgePayload".
 */
export type JudgePayload = JudgePendingCheckTrigger | JudgeRefuse | JudgeVerb | JudgeVerbs;
export type Id1 = number;
export type Kind1 = "act";
export type Text = string;
export type Label4 = string;
export type Value2 = number;
export type Id2 = number;
export type Kind2 = "gm";
export type Text1 = string;
export type Id3 = number;
export type Kind3 = "player";
export type Text2 = string;
export type Id4 = number;
export type Kind4 = "roll";
export type Check = string;
export type Roll = number;
export type Margin = number;
export type Result = "success" | "partial" | "fail";
export type BonusBreakdown = BonusItem[];
/**
 * SSE `log_entry` event payload — discriminated union over `kind`.
 * Wraps domain.memory's 4 sub-classes (GMLogEntry / PlayerLogEntry /
 * ActLogEntry / RollLogEntry) + BonusItem (RollLogEntry sub-shape).
 * Same RootModel pattern as JudgePayload (sub-round 2.6) — codegen
 * emits a clean union alias on the client side.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "LogEntryPayload".
 */
export type LogEntryPayload = GMLogEntry | PlayerLogEntry | ActLogEntry | RollLogEntry;

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
/**
 * Adjacent navigable location, surfaced in the place panel.
 * `difficulty` is the localized tier label (already rendered) or None
 * when the connection has no tier requirement.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "PlaceSurrounding".
 */
export interface PlaceSurrounding {
  name: Name4;
  blurb: Blurb;
  difficulty?: Difficulty;
  risk: RiskBadge;
  [k: string]: unknown;
}
/**
 * Sleep-risk visual atom: localized label + tone hint. Tone is the
 * 3-literal subset (`good`/`neutral`/`bad`) that mapping.labels._RISK_TONES
 * actually emits — domain `EncounterRisk` is a closed 3-value Literal so
 * no fallback default ever fires. Sub-set of client `Tone` (9-literal),
 * so client assignment is safe.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "RiskBadge".
 */
export interface RiskBadge {
  label: Label3;
  tone: Tone1;
  [k: string]: unknown;
}
/**
 * Other inhabitants in the same location, visible to the player.
 * `blurb` is appearance-or-description for living NPCs, `"죽음"` for the dead.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "PlaceTarget".
 */
export interface PlaceTarget {
  name: Name5;
  level: Level2;
  raceJob: Racejob2;
  gender: Gender2;
  blurb: Blurb1;
  trust: Trust1;
  [k: string]: unknown;
}
/**
 * Wire shape for the `place` slot inside the `state` payload.
 * Field order matches mapping/to_front.to_place's dict insertion order.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "PlacePayload".
 */
export interface PlacePayload {
  name: Name6;
  description: Description;
  dayPhase: Dayphase;
  weather: Weather;
  features: Features;
  surroundings: Surroundings;
  targets: Targets;
  risk: RiskBadge;
  [k: string]: unknown;
}
/**
 * Semantic-fallback or verb-driven uncertainty path: judge declared an
 * immediate stat check before any verb dispatches.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "JudgePendingCheckTrigger".
 */
export interface JudgePendingCheckTrigger {
  judge_kind: JudgeKind;
  tier: Tier;
  stat: Stat1;
  targets: Targets1;
  reason: Reason1;
  [k: string]: unknown;
}
/**
 * Player input rejected at the judge layer (out_of_game / meta_breaking).
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "JudgeRefuse".
 */
export interface JudgeRefuse {
  judge_kind: JudgeKind1;
  refuse: RefuseReason;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "RefuseReason".
 */
export interface RefuseReason {
  category: Category;
  message_hint: MessageHint;
}
/**
 * Single verb classification — most common branch.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "JudgeVerb".
 */
export interface JudgeVerb {
  judge_kind: JudgeKind2;
  verb: Verb;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "Verb".
 */
export interface Verb {
  name: Name7;
  target_ids?: TargetIds;
  modifiers?: Modifiers;
}
export interface Modifiers {
  [k: string]: unknown;
}
/**
 * Multi-verb chain (out-of-combat only). Field name is `actions` to
 * match the existing wire shape consumed by the client.
 *
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "JudgeVerbs".
 */
export interface JudgeVerbs {
  judge_kind: JudgeKind3;
  actions: Actions1;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "ActLogEntry".
 */
export interface ActLogEntry {
  id: Id1;
  kind: Kind1;
  text: Text;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "BonusItem".
 */
export interface BonusItem {
  label: Label4;
  value: Value2;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "GMLogEntry".
 */
export interface GMLogEntry {
  id: Id2;
  kind: Kind2;
  text: Text1;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "PlayerLogEntry".
 */
export interface PlayerLogEntry {
  id: Id3;
  kind: Kind3;
  text: Text2;
  [k: string]: unknown;
}
/**
 * This interface was referenced by `Wire`'s JSON-Schema
 * via the `definition` "RollLogEntry".
 */
export interface RollLogEntry {
  id: Id4;
  kind: Kind4;
  check: Check;
  roll: Roll;
  margin: Margin;
  result: Result;
  bonus_breakdown?: BonusBreakdown;
  [k: string]: unknown;
}
