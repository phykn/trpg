import React from 'react';

import type { LogEntry } from '@/logic/log';
import type {
  FrontState,
  GraphActionClientResponse,
  GraphResultOutcome,
  SuggestionChip,
} from '@/services/wire';

type ApplyState = (state: FrontState, gameId?: string | null) => void;
type SetSuggestions = (next: React.SetStateAction<SuggestionChip[]>) => void;
type GraphActionRequestEvents = {
  onNarrationDelta: (text: string, outcome: GraphResultOutcome) => void;
};
type GraphActionCall = (
  signal: AbortSignal,
  events: GraphActionRequestEvents,
) => Promise<GraphActionClientResponse>;
export type OptimisticLogEntry =
  | { kind: 'gm'; text: string }
  | { kind: 'player'; text: string }
  | { kind: 'act'; text: string };

export type GraphActionRequestRuntime = {
  requestInFlightRef: React.MutableRefObject<boolean>;
  abortControllerRef: React.MutableRefObject<AbortController | null>;
  requestGenerationRef: React.MutableRefObject<number>;
  setRequestInFlight: (value: boolean) => void;
  setErrorMessage: (message: string | null) => void;
  setLog: React.Dispatch<React.SetStateAction<LogEntry[]>>;
  setSuggestions: SetSuggestions;
  applyState: ApplyState;
  isActiveGameId?: (gameId: string) => boolean;
};

function mergeEntry(log: LogEntry[], entry: LogEntry): LogEntry[] {
  const idx = log.findIndex((e) => e.id === entry.id);
  if (idx === -1) return [...log, entry];
  const next = log.slice();
  next[idx] = entry;
  return next;
}

function createOptimisticLogEntry(
  entry: OptimisticLogEntry,
  generation: number,
  index: number,
): LogEntry {
  return {
    id: -(generation * 1000 + index + 1),
    ...entry,
  };
}

function appendOptimisticLogEntries(
  runtime: GraphActionRequestRuntime,
  generation: number,
  entries: OptimisticLogEntry[],
): void {
  if (entries.length === 0) return;
  runtime.setLog((current) => [
    ...current,
    ...entries.map((entry, index) => createOptimisticLogEntry(entry, generation, index)),
  ]);
}

function appendStreamingNarration(
  runtime: GraphActionRequestRuntime,
  generation: number,
  optimisticEntryCount: number,
  text: string,
  outcome: GraphResultOutcome,
): void {
  if (!text) return;
  const id = -(generation * 1000 + optimisticEntryCount + 1);
  runtime.setLog((current) => {
    const existing = current.find((entry) => entry.id === id);
    return mergeEntry(current, {
      id,
      kind: 'gm',
      text: `${existing?.kind === 'gm' ? existing.text : ''}${text}`,
      outcome,
    });
  });
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError';
}

export function abortGraphActionRequest(runtime: GraphActionRequestRuntime): void {
  const controller = runtime.abortControllerRef.current;
  if (!runtime.requestInFlightRef.current && !controller) return;
  runtime.requestGenerationRef.current += 1;
  runtime.requestInFlightRef.current = false;
  runtime.abortControllerRef.current = null;
  controller?.abort();
  runtime.setRequestInFlight(false);
}

export async function runGraphActionRequestOnce(
  call: GraphActionCall,
  runtime: GraphActionRequestRuntime,
  optimisticEntries: OptimisticLogEntry[] = [],
): Promise<void> {
  if (runtime.requestInFlightRef.current) return;
  const generation = runtime.requestGenerationRef.current + 1;
  const controller = new AbortController();
  runtime.requestGenerationRef.current = generation;
  runtime.abortControllerRef.current = controller;
  runtime.requestInFlightRef.current = true;
  runtime.setRequestInFlight(true);
  runtime.setErrorMessage(null);
  runtime.setSuggestions([]);
  appendOptimisticLogEntries(runtime, generation, optimisticEntries);
  try {
    const response = await call(controller.signal, {
      onNarrationDelta: (text: string, outcome: GraphResultOutcome) => {
        if (
          runtime.requestGenerationRef.current !== generation
          || controller.signal.aborted
        ) {
          return;
        }
        appendStreamingNarration(runtime, generation, optimisticEntries.length, text, outcome);
      },
    });
    if (runtime.requestGenerationRef.current !== generation) return;
    if (runtime.isActiveGameId && !runtime.isActiveGameId(response.game_id)) return;
    runtime.applyState(response.state, response.game_id);
    runtime.setSuggestions(response.suggestions);
    if (response.message) {
      runtime.setLog((current) =>
        mergeEntry(current, {
          id: -Date.now(),
          kind: 'gm',
          text: response.message ?? '',
        }),
      );
    }
  } catch (err) {
    if (
      runtime.requestGenerationRef.current !== generation
      || controller.signal.aborted
      || isAbortError(err)
    ) {
      return;
    }
    runtime.setErrorMessage(err instanceof Error ? err.message : String(err));
  } finally {
    if (runtime.requestGenerationRef.current === generation) {
      runtime.abortControllerRef.current = null;
      runtime.requestInFlightRef.current = false;
      runtime.setRequestInFlight(false);
    }
  }
}

export function useGraphActionRunner({
  applyState,
  setErrorMessage,
  setLog,
  setSuggestions,
  isActiveGameId,
}: {
  applyState: ApplyState;
  setErrorMessage: (message: string | null) => void;
  setLog: React.Dispatch<React.SetStateAction<LogEntry[]>>;
  setSuggestions: SetSuggestions;
  isActiveGameId?: (gameId: string) => boolean;
}) {
  const [requestInFlight, setRequestInFlight] = React.useState(false);
  const requestInFlightRef = React.useRef(false);
  const abortControllerRef = React.useRef<AbortController | null>(null);
  const requestGenerationRef = React.useRef(0);

  const runGraphActionRequest = React.useCallback(
    async (call: GraphActionCall, optimisticEntries: OptimisticLogEntry[] = []) => {
      await runGraphActionRequestOnce(call, {
        requestInFlightRef,
        abortControllerRef,
        requestGenerationRef,
        setRequestInFlight,
        setErrorMessage,
        setLog,
        setSuggestions,
        applyState,
        isActiveGameId,
      }, optimisticEntries);
    },
    [applyState, isActiveGameId, setErrorMessage, setLog, setSuggestions],
  );

  const abortRequest = React.useCallback(
    () => {
      abortGraphActionRequest({
        requestInFlightRef,
        abortControllerRef,
        requestGenerationRef,
        setRequestInFlight,
        setErrorMessage,
        setLog,
        setSuggestions,
        applyState,
        isActiveGameId,
      });
    },
    [applyState, isActiveGameId, setErrorMessage, setLog, setSuggestions],
  );

  return {
    requestInFlight,
    requestInFlightRef,
    runGraphActionRequest,
    abortGraphActionRequest: abortRequest,
  };
}
