import { useEffect, useState } from 'react';

// Text arrives a poll at a time, a dozen words at once; the screen lets it out a few letters every TICK instead,
// spreading what is waiting over about one poll, so it reads as typed and catches up when it falls behind.
export const TICK = 100;
const SPREAD = 12;

export function nextShown(shown: string, full: string): string {
  if (!full.startsWith(shown)) return full;   // rewritten or cleared: show it as it is
  const waiting = full.length - shown.length;
  return waiting ? full.slice(0, shown.length + Math.max(1, Math.ceil(waiting / SPREAD))) : shown;
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
