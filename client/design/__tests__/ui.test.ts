import { cn, control, text } from '../ui';

test('a later class replaces the one it fights, and our size names are sizes, not colors', () => {
  expect(control({ kind: 'tab' }, 'px-4')).not.toContain('px-1');
  expect(text({ kind: 'label', on: true }).split(' ')).toEqual(expect.arrayContaining(['text-panel', 'text-fg-on-emphasis']));
  expect(text({ kind: 'label', on: true })).not.toContain('text-fg-default');
  expect(cn('text-chip text-fg-muted', 'text-gold-fg')).toBe('text-chip text-gold-fg');
});
