import type { FrontState, PendingCheck } from '@/types/domain';
import type { LogEntry } from '@/types/ui';
import type { StreamEvent } from '@/types/wire';

export type StreamHandlers = {
  setPending: (p: PendingCheck) => void;
  clearPending: () => void;
  appendStreamingText: (t: string) => void;
  clearStreamingText: () => void;
  upsertLogEntry: (e: LogEntry) => void;
  applyState: (s: FrontState) => void;
  clearCombat: () => void;
  setSuggestions: (items: string[]) => void;
  setErrorMessage: (m: string) => void;
};

export function handleStreamEvent(ev: StreamEvent, h: StreamHandlers): void {
  switch (ev.type) {
    case 'judge':
      return;
    case 'pending_check':
      h.setPending(ev.data);
      return;
    case 'narrative_delta':
      h.appendStreamingText(ev.data.text);
      return;
    case 'suggestions':
      h.setSuggestions(ev.data.items);
      return;
    case 'log_entry':
      h.upsertLogEntry(ev.data);
      // Roll resolved → clear pending so the rolling indicator drops as soon
      // as the dice number lands, instead of lingering through the entire GM
      // narration that follows.
      if (ev.data.kind === 'roll') h.clearPending();
      return;
    case 'state':
      h.applyState(ev.data);
      h.clearStreamingText();
      return;
    case 'combat_start':
    case 'combat_turn':
      // The auto-combat sim runs the entire fight (or up to the round cap)
      // server-side and streams the cinematic body via narrative_delta.
      // combat_start fires once at fight entry; combat_turn fires once per
      // actor action across all rounds in the cycle. Both are observability
      // signals — `state` (after finalize) and `log_entry` (cinematic gm
      // body + numeric act summary) are authoritative for the UI.
      return;
    case 'combat_end':
      // Terminal outcomes only (victory / defeat / fled / downed). The
      // `ongoing` outcome (round cap reached, both sides still standing)
      // does not fire combat_end — combat_state stays live so the next
      // /turn picks up where this cycle left off.
      h.clearCombat();
      return;
    case 'done':
      return;
    case 'error':
      h.setErrorMessage(ev.data.message);
      return;
  }
}
