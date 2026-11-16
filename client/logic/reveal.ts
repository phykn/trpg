import { useEffect, useState } from 'react';

// A text arrives whole once checked; the screen lets it out a couple of letters every TICK so it reads as typed,
// and faster when much is waiting, so a long ending does not keep the commands locked for long.
export const TICK = 100;
const STEP = 2;
const SPREAD = 40;

export function nextShown(shown: string, full: string): string {
  if (!full.startsWith(shown)) return full;   // rewritten or cleared: show it as it is
  const waiting = full.length - shown.length;
  return waiting ? full.slice(0, shown.length + Math.max(STEP, Math.ceil(waiting / SPREAD))) : shown;
}

// A line mounted with its text (an earlier turn) shows at once; one that fills while on screen is let out.
export function useReveal(full: string): string {
  const [shown, setShown] = useState(full);
  useEffect(() => {
    if (shown === full) return undefined;
    if (!full.startsWith(shown)) {
      setShown(full);
      return undefined;
    }
    const id = setTimeout(() => setShown((s) => nextShown(s, full)), TICK);
    return () => clearTimeout(id);
  }, [full, shown]);
  return shown;
}
