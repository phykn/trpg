import { ScrollView, Text, View } from 'react-native';
import Animated from 'react-native-reanimated';

import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { useEnter } from '@/components/ui/motion';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

function Chapter({ k, text, delay }: { k: number; text: string; delay: number }) {
  const enter = useEnter(10, delay);
  return (
    <Animated.View style={enter}>
      <View className="gap-1">
        <Text className="font-sans-semibold text-chip text-gold-fg">{ko.chapterNo(k)}</Text>
        <Text className="font-sans text-body text-fg-default">{text}</Text>
      </View>
    </Animated.View>
  );
}

export function Ending({ view, recaps, onNew }: { view: GameView; recaps: Record<number, string>; onNew: () => void }) {
  const chapters = [...new Set([...view.recaps, ...Object.keys(recaps).map(Number)])].sort((a, b) => a - b);
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
        {chapters.map((k, i) => <Chapter key={k} k={k} text={recaps[k] ?? ''} delay={150 + i * 120} />)}
        {view.journal.choices.length ? (
          <View className="gap-1.5 rounded-xl bg-canvas-subtle px-4 py-3">
            {view.journal.choices.map((c, i) => (
              <View key={`${c.name}${i}`} className="flex-row items-center gap-2">
                <Icon name={c.kind === 'fork' ? 'arrow' : 'tag'} size={12} color={colors.fg.subtle} />
                <Text className="font-sans text-panel text-fg-muted">{ko.chapterNo(c.chapter)}</Text>
                <Text className="min-w-0 flex-1 font-sans text-panel text-fg-default">{c.name}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </ScrollView>
      <Button icon="play" label={ko.newGame} onPress={onNew} />
    </View>
  );
}
