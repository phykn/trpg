import React from 'react';
import {
  INITIAL_HERO,
  INITIAL_SUBJECT,
  INITIAL_QUEST,
  INITIAL_PLACE,
  INITIAL_LOG,
  fakeGMReply,
  rollD20,
  resolveCheck,
  checkPrompt,
  rollFollowup,
  PENDING_CHECK,
} from '@/services';
import type { LogEntry } from '@/types/domain';

const GM_REPLY_DELAY = 450;
const CHECK_PROMPT_DELAY = 500;
const ROLL_DURATION = 900;
const ROLL_FOLLOWUP_DELAY = 300;
const FOLLOWUP_CHANCE = 0.5;

export function useGame() {
  const [log, setLog] = React.useState<LogEntry[]>(INITIAL_LOG);
  const [rolling, setRolling] = React.useState(false);
  const [rollEnabled, setRollEnabled] = React.useState(true);

  const nextId = React.useRef(
    INITIAL_LOG.reduce((m, e) => Math.max(m, e.id), 0) + 1,
  );

  const timers = React.useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  React.useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach(clearTimeout);
      pending.clear();
    };
  }, []);

  const schedule = React.useCallback((fn: () => void, ms: number) => {
    const id = setTimeout(() => {
      timers.current.delete(id);
      fn();
    }, ms);
    timers.current.add(id);
  }, []);

  const pushText = (kind: 'gm' | 'player' | 'act', text: string) =>
    setLog((L) => [...L, { id: nextId.current++, kind, text }]);
  const pushRoll = (data: Omit<Extract<LogEntry, { kind: 'roll' }>, 'id' | 'kind'>) =>
    setLog((L) => [...L, { id: nextId.current++, kind: 'roll', ...data }]);

  const onSend = (text: string) => {
    pushText('player', text);
    schedule(() => {
      pushText('gm', fakeGMReply(text));
      if (Math.random() < FOLLOWUP_CHANCE) {
        schedule(() => {
          pushText('act', checkPrompt(PENDING_CHECK));
          setRollEnabled(true);
        }, CHECK_PROMPT_DELAY);
      }
    }, GM_REPLY_DELAY);
  };

  const onRoll = () => {
    if (rolling || !rollEnabled) return;
    setRolling(true);
    setRollEnabled(false);
    schedule(() => {
      const roll = rollD20();
      const result = resolveCheck(PENDING_CHECK, roll);
      pushRoll({ check: PENDING_CHECK.stat, dc: PENDING_CHECK.dc, roll, mod: PENDING_CHECK.mod, result });
      setRolling(false);
      schedule(() => pushText('gm', rollFollowup(result)), ROLL_FOLLOWUP_DELAY);
    }, ROLL_DURATION);
  };

  return {
    hero: INITIAL_HERO,
    subject: INITIAL_SUBJECT,
    quest: INITIAL_QUEST,
    place: INITIAL_PLACE,
    log,
    rolling,
    rollEnabled,
    onSend,
    onRoll,
  };
}
