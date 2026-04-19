import React from 'react';
import {
  INITIAL_HERO,
  INITIAL_SUBJECT,
  INITIAL_QUEST,
  INITIAL_PLACE,
  INITIAL_LOG,
  fakeGMReply,
  rollD20,
} from '@/services';
import type { LogEntry } from '@/types/game';

export function useGame() {
  const [log, setLog] = React.useState<LogEntry[]>(INITIAL_LOG);
  const [rolling, setRolling] = React.useState(false);
  const [rollEnabled, setRollEnabled] = React.useState(true);
  const nextId = React.useRef(INITIAL_LOG.length + 1);

  const pushGM = (text: string) =>
    setLog((L) => [...L, { id: nextId.current++, kind: 'gm', text }]);
  const pushPlayer = (text: string) =>
    setLog((L) => [...L, { id: nextId.current++, kind: 'player', text }]);
  const pushAct = (text: string) =>
    setLog((L) => [...L, { id: nextId.current++, kind: 'act', text }]);
  const pushRoll = (data: Omit<Extract<LogEntry, { kind: 'roll' }>, 'id' | 'kind'>) =>
    setLog((L) => [...L, { id: nextId.current++, kind: 'roll', ...data }]);

  const onSend = (text: string) => {
    pushPlayer(text);
    setTimeout(() => {
      pushGM(fakeGMReply(text));
      if (Math.random() < 0.5) {
        setTimeout(() => {
          pushAct('GM이 판정을 요청합니다 — DEX 체크');
          setRollEnabled(true);
        }, 500);
      }
    }, 450);
  };

  const onRoll = () => {
    if (rolling || !rollEnabled) return;
    setRolling(true);
    setRollEnabled(false);
    setTimeout(() => {
      const r = rollD20(), bonus = 3, total = r + bonus, dc = 12;
      const result: 'success' | 'fail' = total >= dc ? 'success' : 'fail';
      pushRoll({ check: 'DEX', dc, roll: r, mod: bonus, result });
      setRolling(false);
      setTimeout(() => {
        pushGM(result === 'success'
          ? '두목의 시선을 훌륭히 피했다. 기회가 왔다.'
          : '발밑의 자갈이 굴렀다. 두목이 당신을 노려본다.');
      }, 300);
    }, 900);
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
