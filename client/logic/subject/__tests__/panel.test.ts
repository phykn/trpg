import { buildSubjectSlot } from '../panel';
import type { Subject } from '../types';

const subject: Subject = {
  name: '여관 주인',
  alive: true,
  role: '주인',
  raceJob: '인간',
  gender: '남성',
  level: 1,
};

describe('buildSubjectSlot', () => {
  test('uses NPC as the stable top chip label', () => {
    expect(buildSubjectSlot(null).chip.short).toBe('NPC');
    expect(buildSubjectSlot(subject).chip.short).toBe('NPC');
  });

  test('shows only public subject summary fields', () => {
    const slot = buildSubjectSlot(subject);

    expect(slot.chip).not.toHaveProperty('detail');
    expect(slot.panel?.bar).toBeUndefined();
    expect(slot.panel?.sections?.map((section) => section.label)).toEqual(['역할']);
  });
});
