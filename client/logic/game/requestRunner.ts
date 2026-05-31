import React from 'react';

import type { LogEntry } from '@/logic/log';
import type {
  FrontState,
  GraphActionClientResponse,
  GraphResultOutcome,
  SuggestionChip,
} from '@/services/wire';
import { errorMessageForDisplay } from './errors';

type ApplyState = (state: FrontState, gameId?: string | null) => void;
type SetSuggestions = (next: React.SetStateAction<SuggestionChip[]>) => void;
type GraphActionRequestEvents = {
  onResult: (response: GraphActionClientResponse) => void;
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
  const id = streamingNarrationId(generation, optimisticEntryCount);
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

function streamingNarrationId(generation: number, optimisticEntryCount: number): number {
  return -(generation * 1000 + optimisticEntryCount + 1);
}

function removeStreamingNarration(
  runtime: GraphActionRequestRuntime,
  generation: number,
  optimisticEntryCount: number,
): void {
  const id = streamingNarrationId(generation, optimisticEntryCount);
  runtime.setLog((current) => current.filter((entry) => entry.id !== id));
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError';
}

function shouldLogGraphRequestDebug(): boolean {
  if (process.env.EXPO_PUBLIC_GRAPH_DEBUG === '1') return true;
  if (process.env.EXPO_PUBLIC_GRAPH_DEBUG === '0') return false;
  const apiUrl = process.env.EXPO_PUBLIC_API_URL ?? '';
  return process.env.NODE_ENV !== 'test' && (__DEV__ || apiUrl.includes(':8001'));
}

function graphRequestDebug(
  phase: string,
  fields: Record<string, unknown>,
): void {
  if (!shouldLogGraphRequestDebug()) return;
  console.debug(`[trpg:graph-request] ${JSON.stringify({ phase, ...fields })}`);
}

export function abortGraphActionRequest(runtime: GraphActionRequestRuntime): void {
  const controller = runtime.abortControllerRef.current;
  if (!runtime.requestInFlightRef.current && !controller) return;
  runtime.requestGenerationRef.current += 1;
  graphRequestDebug('abort', { generation: runtime.requestGenerationRef.current });
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
  const startedAt = Date.now();
  runtime.requestGenerationRef.current = generation;
  runtime.abortControllerRef.current = controller;
  runtime.requestInFlightRef.current = true;
  runtime.setRequestInFlight(true);
  runtime.setErrorMessage(null);
  runtime.setSuggestions([]);
  graphRequestDebug('start', {
    generation,
    optimisticEntries: optimisticEntries.length,
  });
  appendOptimisticLogEntries(runtime, generation, optimisticEntries);
  try {
    const response = await call(controller.signal, {
      onResult: (result: GraphActionClientResponse) => {
        if (
          runtime.requestGenerationRef.current !== generation
          || controller.signal.aborted
        ) {
          return;
        }
        if (runtime.isActiveGameId && !runtime.isActiveGameId(result.game_id)) return;
        graphRequestDebug('result', {
          generation,
          gameId: result.game_id,
          status: result.status ?? null,
          pendingConfirmation: result.pendingConfirmation !== null,
          pendingRoll: result.pendingRoll !== null,
          elapsedMs: Date.now() - startedAt,
        });
        runtime.applyState(result.state, result.game_id);
      },
      onNarrationDelta: (text: string, outcome: GraphResultOutcome) => {
        if (
          runtime.requestGenerationRef.current !== generation
          || controller.signal.aborted
        ) {
          return;
        }
        graphRequestDebug('delta', {
          generation,
          chars: text.length,
          outcome,
          elapsedMs: Date.now() - startedAt,
        });
        appendStreamingNarration(runtime, generation, optimisticEntries.length, text, outcome);
      },
    });
    if (runtime.requestGenerationRef.current !== generation) return;
    if (runtime.isActiveGameId && !runtime.isActiveGameId(response.game_id)) return;
    graphRequestDebug('final', {
      generation,
      gameId: response.game_id,
      status: response.status ?? null,
      pendingConfirmation: response.pendingConfirmation !== null,
      pendingRoll: response.pendingRoll !== null,
      suggestions: response.suggestions.length,
      elapsedMs: Date.now() - startedAt,
    });
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
      graphRequestDebug('aborted', {
        generation,
        elapsedMs: Date.now() - startedAt,
      });
      return;
    }
    removeStreamingNarration(runtime, generation, optimisticEntries.length);
    graphRequestDebug('error', {
      generation,
      error: err instanceof Error ? err.message : String(err),
      elapsedMs: Date.now() - startedAt,
    });
    runtime.setErrorMessage(errorMessageForDisplay(err));
  } finally {
    if (runtime.requestGenerationRef.current === generation) {
      runtime.abortControllerRef.current = null;
      runtime.requestInFlightRef.current = false;
      runtime.setRequestInFlight(false);
      graphRequestDebug('done', {
        generation,
        elapsedMs: Date.now() - startedAt,
      });
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
