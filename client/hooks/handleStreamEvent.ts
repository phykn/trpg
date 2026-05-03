import type { LogEntry } from '@/features/log';
import type { FrontState, PendingCheck, StreamEvent } from '@/types/wire';

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
      // Drop the rolling indicator the moment the dice lands, not after the GM narration finishes.
      if (ev.data.kind === 'roll') h.clearPending();
      // The gm log_entry signals streaming is done — clear the in-flight text so
      // reaction cards (affinity, quest-start) that arrive next render after, not above.
      if (ev.data.kind === 'gm') h.clearStreamingText();
      return;
    case 'state':
      h.applyState(ev.data);
      h.clearStreamingText();
      return;
    case 'combat_start':
    case 'combat_turn':
      // Observability only; UI reads from `state` + `log_entry`.
      return;
    case 'combat_end':
      // Fires for terminal outcomes only — `ongoing` keeps combat_state live for the next /turn.
      h.clearCombat();
      return;
    case 'done':
      return;
    case 'error':
      h.setErrorMessage(ev.data.message);
      return;
  }
}
