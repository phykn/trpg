import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { Sheet } from '@/components/ui/Sheet';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

type Growth = GameView['growth'][number];

// Growth reads by kind: the same icons as the hero sheet head each group, so no group needs a title.
const KINDS: { kind: Growth['kind']; icon: IconName }[] = [
  { kind: 'approach', icon: 'bolt' }, { kind: 'trait', icon: 'star' }, { kind: 'wound', icon: 'tag' },
];

// Raising a stat is a 2×2 grid; swaps and healings are one per line because their names are longer. A swap says what
// the new trait knows, as the start screen does.
function Tile({ g, onPick }: { g: Growth; onPick: (action: string) => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={g.text ? `${g.label}, ${g.text}` : g.label}
      onPress={() => onPick(g.action)} style={pressed}
      className="min-h-[44px] flex-1 items-center justify-center rounded-xl border border-border-default bg-canvas-subtle px-3 py-1.5">
      <Text className="font-sans-semibold text-body text-fg-default">{g.name}</Text>
      {g.text ? <Text className="text-center font-sans text-chip text-fg-muted">{g.text}</Text> : null}
    </Pressable>
  );
}

function rows<T>(items: T[], n: number): T[][] {
  return Array.from({ length: Math.ceil(items.length / n) }, (_, i) => items.slice(i * n, i * n + n));
}

export function GrowthCard({ growth, onPick, onLater }: { growth: Growth[]; onPick: (action: string) => void; onLater: () => void }) {
  return (
    <Sheet title={ko.growth} icon="spark" onClose={onLater}>
      {KINDS.map(({ kind, icon }) => {
        const items = growth.filter((g) => g.kind === kind);
        if (!items.length) return null;
        return (
          <View key={kind} className="flex-row gap-3">
            <View className="h-11 w-5 items-center justify-center"><Icon name={icon} size={16} color={colors.gold.fg} /></View>
            <View className="min-w-0 flex-1 gap-2">
              {rows(items, kind === 'approach' ? 2 : 1).map((r) => (
                <View key={r[0].action} className="flex-row gap-2">
                  {r.map((g) => <Tile key={g.action} g={g} onPick={onPick} />)}
                  {r.length < (kind === 'approach' ? 2 : 1) ? <View className="flex-1" /> : null}
                </View>
              ))}
            </View>
          </View>
        );
      })}
    </Sheet>
  );
}
