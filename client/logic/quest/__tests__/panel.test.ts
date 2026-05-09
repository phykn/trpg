import { buildQuestSlot } from '../panel';
import type { Quest } from '../types';

const quest = (actions: Quest['actions']): Quest => ({
  id: 'quest_01',
  title: '첫 의뢰',
  summary: '광장의 문제를 해결합니다.',
  giver: '촌장',
  difficulty: { label: '보통', tone: 'neutral' },
  goals: ['늑대 쫓아내기'],
  progressLabel: '0/1',
  rewards: { gold: 5, exp: 10 },
  status: 'active',
  actions,
});

describe('buildQuestSlot', () => {
  test('leaves quest action confirmation to the server pendingConfirmation flow', () => {
    const slot = buildQuestSlot(quest(['accept', 'abandon']));

    const items = slot.panel?.actions?.[0]?.items ?? [];

    expect(items).toHaveLength(2);
    expect(items.every((item) => item.kind === 'quest_action' && item.confirm === undefined)).toBe(true);
  });
});
