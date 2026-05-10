import { meterDisplay } from '../HeroStrip';

describe('meterDisplay', () => {
  test('renders experience as current percent only', () => {
    expect(meterDisplay(100, 100, 'percent')).toBe('100%');
    expect(meterDisplay(5, 20, 'percent')).toBe('25%');
  });

  test('renders revival as remaining count only', () => {
    expect(meterDisplay(0, 3, 'current')).toBe('0');
    expect(meterDisplay(2, 3, 'current')).toBe('2');
  });
});
