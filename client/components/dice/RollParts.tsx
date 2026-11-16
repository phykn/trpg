import { Text, View } from 'react-native';

import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { cn, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { RollResult } from '@/services/types';

// The pieces of a roll, read left to right without dots: what it needs, what came, and so whether it passed.
// The chat line and the dice sheet both build from these.
export const signed = (n: number) => (n > 0 ? `+${n}` : `${n}`);

export function Need({ need, large }: { need: number; large?: boolean }) {
  return <Text className={text({ kind: 'need' }, large && 'border-2 px-4 py-1 text-title text-fg-default')}>{ko.need(need)}</Text>;
}

// "6 (5 + 1 + 1)": the total first, then how it was made.
export function Sum({ result, large }: { result: Pick<RollResult, 'eyes' | 'add' | 'total' | 'won'>; large?: boolean }) {
  const add = result.add ? ` ${result.add > 0 ? '+' : '-'} ${Math.abs(result.add)}` : '';
  return (
    <View className="flex-row items-baseline gap-1.5">
      <Text className={text({ kind: 'total' }, large && 'text-hero', result.won ? 'text-health-fg' : 'text-danger-fg')}>
        {result.total}
      </Text>
      <Text className={text({ kind: 'note' })}>({result.eyes.join(' + ')}{add})</Text>
    </View>
  );
}

export function Verdict({ won, large }: { won: boolean; large?: boolean }) {
  const color = won ? colors.health.fg : colors.danger.fg;
  return (
    <View className="flex-row items-center gap-1">
      <Icon name={won ? 'won' : 'lost'} size={large ? icon.lg : icon.md} color={color} width={2} />
      <Text className={cn(text({ kind: large ? 'title' : 'label' }), won ? 'text-health-fg' : 'text-danger-fg')}>
        {won ? ko.won : ko.lost}
      </Text>
    </View>
  );
}

// The line a roll leaves in the chat: 🎲 몰아세운다 (8 이상) 6 (5 + 1) ✕ 실패
export function RollLine({ result }: { result: RollResult }) {
  return (
    <View accessibilityLabel={`${result.method} ${ko.need(result.need)} ${result.total} ${result.won ? ko.won : ko.lost}`}
      className="flex-row flex-wrap items-center gap-x-2 gap-y-1 self-start">
      <Icon name="dice" size={icon.md} color={colors.fg.muted} width={2} />
      <Text className={text({ kind: 'label' })}>{result.method}</Text>
      <Need need={result.need} />
      <Sum result={result} />
      <Verdict won={result.won} />
    </View>
  );
}
