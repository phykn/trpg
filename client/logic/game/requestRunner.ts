import React from 'react';

import type { LogEntry } from '@/logic/log';
import type { FrontState, GraphActionClientResponse } from '@/services/wire';

type ApplyState = (state: FrontState, gameId?: string | null) => void;
type SetSuggestions = (next: React.SetStateAction<string[]>) => void;

function mergeEntry(log: LogEntry[], entry: LogEntry): LogEntry[] {
  const idx = log.findIndex((e) => e.id === entry.id);
  if (idx === -1) return [...log, entry];
  const next = log.slice();
  next[idx] = entry;
  return next;
}

export function useGraphActionRunner({
  applyState,
  setErrorMessage,
  setLog,
  setSuggestions,
}: {
  applyState: ApplyState;
  setErrorMessage: (message: string | null) => void;
  setLog: React.Dispatch<React.SetStateAction<LogEntry[]>>;
  setSuggestions: SetSuggestions;
}) {
  const [requestInFlight, setRequestInFlight] = React.useState(false);
  const requestInFlightRef = React.useRef(false);

  const runGraphActionRequest = React.useCallback(
    async (call: () => Promise<GraphActionClientResponse>) => {
      if (requestInFlightRef.current) return;
      requestInFlightRef.current = true;
      setRequestInFlight(true);
      setErrorMessage(null);
      setSuggestions([]);
      try {
        const response = await call();
        applyState(response.state, response.game_id);
        setSuggestions(response.suggestions);
        if (response.message) {
          setLog((current) =>
            mergeEntry(current, {
              id: -Date.now(),
              kind: 'gm',
              text: response.message ?? '',
            }),
          );
        }
      } catch (err) {
        setErrorMessage(err instanceof Error ? err.message : String(err));
      } finally {
        requestInFlightRef.current = false;
        setRequestInFlight(false);
      }
    },
    [applyState, setErrorMessage, setLog, setSuggestions],
  );

  return {
    requestInFlight,
    requestInFlightRef,
    runGraphActionRequest,
  };
}
