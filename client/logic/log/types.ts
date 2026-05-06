import type {
  BonusItem as BonusItemPayload,
  LogEntryPayload,
  RollLogEntry,
} from '@/services/wire.gen';

// Re-export auto-generated wire shapes under historical client names.
// Caller code (LogItem, useGame, wire.ts) keeps using `LogEntry` /
// `BonusItem` / `RollResult`. RollResult uses indexed access so it
// survives codegen renaming of the `result` literal.
export type LogEntry = LogEntryPayload;
export type BonusItem = BonusItemPayload;
export type RollResult = RollLogEntry["result"];
