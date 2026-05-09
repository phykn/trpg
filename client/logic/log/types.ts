import type {
  LogEntryPayload,
  RollLogEntry,
} from '@/services/wire.gen';

// RollResult uses indexed access so it survives codegen renaming of the
// `result` literal.
export type LogEntry = LogEntryPayload;
export type RollResult = RollLogEntry["result"];
