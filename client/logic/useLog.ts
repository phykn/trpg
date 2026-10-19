import { useCallback, useEffect, useRef, useState } from 'react';

import { loadLog, storeLog } from '@/services/storage';

export type Entry =
  | { id: string; kind: 'you' | 'story'; text: string }
  | { id: string; kind: 'roll'; d1: number; d2: number; total: number; result: string };

const CAP = 300;

export function useLog(gameId: string | null, premise: string | null) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const ref = useRef(entries);
  ref.current = entries;

  useEffect(() => {
    if (!gameId) { setEntries([]); return; }
    const saved = loadLog<Entry>(gameId);
    setEntries(saved.length || !premise ? saved : [{ id: 'premise', kind: 'story', text: premise }]);
  }, [gameId, premise]);

  // Ids carry the turn, so replaying a turn after a reload never doubles it.
  const add = useCallback((...more: Entry[]) => {
    if (!gameId) return;
    const have = new Set(ref.current.map((e) => e.id));
    const fresh = more.filter((e) => !have.has(e.id));
    if (!fresh.length) return;
    const next = [...ref.current, ...fresh].slice(-CAP);
    ref.current = next;
    setEntries(next);
    storeLog(gameId, next);
  }, [gameId]);

  const has = useCallback((id: string) => ref.current.some((e) => e.id === id), []);
  return { entries, add, has };
}
