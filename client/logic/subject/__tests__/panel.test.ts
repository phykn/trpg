import { buildSubjectSlot } from '../panel';
import type { Subject } from '../types';

const subject: Subject = {
  name: '여관 주인',
  alive: true,
  role: '주인',
  raceJob: '인간',
  gender: '남성',
  trust: 4,
  known: ['불안한 표정으로 뒷문을 살핍니다.'],
  level: 1,
  hp: 18,
  hpMax: 18,
  stats: [{ label: '몸', value: 9 }],
  equipment: { weapon: null, armor: null, accessory: null },
  inventory: [],
  skills: [],
};

describe('buildSubjectSlot', () => {
  test('uses NPC as the stable top chip label', () => {
    expect(buildSubjectSlot(null).chip.short).toBe('NPC');
    expect(buildSubjectSlot(subject).chip.short).toBe('NPC');
  });
});
