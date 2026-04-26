import type { FrontState } from '@/types/domain';
import type { LogEntry } from '@/types/ui';
import type { PendingCheck, StreamEvent } from '@/types/wire';

export type StreamHandlers = {
  setPending: (p: PendingCheck) => void;
  appendStreamingText: (t: string) => void;
  clearStreamingText: () => void;
  upsertLogEntry: (e: LogEntry) => void;
  applyState: (s: FrontState) => void;
  clearCombat: () => void;
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
    case 'log_entry':
      h.upsertLogEntry(ev.data);
      return;
    case 'state':
      h.applyState(ev.data);
      h.clearStreamingText();
      return;
    case 'combat_start':
    case 'combat_turn':
      // SSE state is authoritative — round end emits a state event.
      // log_entry carries the in-round Korean prose.
      return;
    case 'combat_end':
      h.clearCombat();
      return;
    case 'done':
      return;
    case 'error':
      h.setErrorMessage(ev.data.message);
      return;
  }
}
