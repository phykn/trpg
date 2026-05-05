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
