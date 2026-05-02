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
      // Drop the rolling indicator the moment the dice lands, not after the GM narration finishes.
      if (ev.data.kind === 'roll') h.clearPending();
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
