import React from 'react';
import { rollD20, resolveCheck } from '@/services';
import {
  INITIAL_HERO,
  INITIAL_SUBJECT,
  INITIAL_QUEST,
  INITIAL_PLACE,
  INITIAL_LOG,
  checkPrompt,
  rollFollowup,
  PENDING_CHECK,
} from '@/debug';
import { testStream } from '@/debug/llm-test';
import type { LogEntry } from '@/types/domain';

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
  const aborts = React.useRef<Set<AbortController>>(new Set());
  React.useEffect(() => {
    const pendingTimers = timers.current;
    const pendingAborts = aborts.current;
    return () => {
      pendingTimers.forEach(clearTimeout);
      pendingTimers.clear();
      pendingAborts.forEach((a) => a.abort());
      pendingAborts.clear();
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
    const gmId = nextId.current++;
    setLog((L) => [...L, { id: gmId, kind: 'gm', text: '' }]);

    const controller = new AbortController();
    aborts.current.add(controller);

    const appendGm = (delta: string) =>
      setLog((L) =>
        L.map((e) =>
          e.id === gmId && e.kind === 'gm' ? { ...e, text: e.text + delta } : e,
        ),
      );

    testStream(
      { query: text, think: false },
      (chunk) => {
        if (chunk.answer) appendGm(chunk.answer);
      },
      controller.signal,
    )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const msg = err instanceof Error ? err.message : String(err);
        appendGm(`\n[연결 실패: ${msg}]`);
      })
      .finally(() => {
        aborts.current.delete(controller);
        if (controller.signal.aborted) return;
        if (Math.random() < FOLLOWUP_CHANCE) {
          schedule(() => {
            pushText('act', checkPrompt(PENDING_CHECK));
            setRollEnabled(true);
          }, CHECK_PROMPT_DELAY);
        }
      });
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
