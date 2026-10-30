import { ScrollView, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { Button } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { useEnter } from '@/components/ui/motion';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

const LEDGER_ICON = { give: 'bag', promise: 'book', follow: 'user', regards: 'heart' } as const;

type Line = { icon: IconName; text: string };

function Chapter({ k, text, lines, delay }: { k: number; text: string; lines: Line[]; delay: number }) {
  const enter = useEnter(10, delay);
  return (
    <Animated.View style={enter}>
      <View className="gap-1">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.chapterNo(k)}</Text>
        {text ? <Text className="font-sans text-body text-fg-default">{text}</Text> : null}
        {lines.length ? (
          <View className="mt-1 gap-1.5 rounded-xl bg-canvas-subtle px-4 py-3">
            {lines.map((l, i) => (
              <View key={`${l.text}${i}`} className="flex-row items-center gap-2">
                <Icon name={l.icon} size={12} color={colors.fg.subtle} />
                <Text className="min-w-0 flex-1 font-sans text-panel text-fg-default">{l.text}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>
    </Animated.View>
  );
}

export function Ending({ view, recaps, onNew }: { view: GameView; recaps: Record<number, string>; onNew: () => void }) {
  // Per chapter, the recap and then the ledger: what was chosen, and what passed with people (ui.md 5.4).
  const ledger = view.ledger ?? [];      // a view saved before the ledger existed has none
  const lines = (k: number): Line[] => [
    ...view.journal.choices.filter((c) => c.chapter === k)
      .map((c) => ({ icon: (c.kind === 'fork' ? 'arrow' : 'tag') as IconName, text: c.name })),
    ...(ledger.find((x) => x.chapter === k)?.lines ?? []).map((l) => ({ icon: LEDGER_ICON[l.kind], text: l.text })),
  ];
  const chapters = [...new Set([...view.recaps, ...Object.keys(recaps).map(Number),
    ...ledger.map((x) => x.chapter), ...view.journal.choices.map((c) => c.chapter)])].sort((a, b) => a - b);
  const title = useEnter(12);
  return (
    <View className="min-h-0 flex-1 px-4 pb-3">
      <ScrollView showsVerticalScrollIndicator={false} className="min-h-0 flex-1" contentContainerStyle={{ gap: 18, paddingVertical: 20 }}>
        <Animated.View style={title}>
          <View className="items-center gap-3">
            <Icon name="star" size={22} color={colors.gold.fg} />
            <Text accessibilityRole="header" className="text-center font-serif text-hero text-gold-fg">{view.ending?.title}</Text>
            <View className="h-[1px] w-10 bg-gold-fg" />
          </View>
        </Animated.View>
        {chapters.map((k, i) => <Chapter key={k} k={k} text={recaps[k] ?? ''} lines={lines(k)} delay={150 + i * 120} />)}
      </ScrollView>
      <Button icon="plus" label={ko.begin} onPress={onNew} />
    </View>
  );
}
