import { Pressable, Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

/** ui.md 5.4: the ending's title, a recap per chapter, and the costs and forks chosen. */
export function Ending({ view, recaps, onNew }: { view: GameView; recaps: Record<number, string>; onNew: () => void }) {
  return (
    <View className="flex-1 gap-3 px-4 py-4">
      <Text accessibilityRole="header" className="font-sans-semibold text-hero text-gold-fg">{view.ending?.title}</Text>
      {view.recaps.map((k) => (
        <View key={k} className="gap-1">
          <Text className="font-sans-semibold text-panel text-fg-muted">{ko.chapterNo(k)}</Text>
          <Text className="font-sans text-body text-fg-default">{recaps[k] ?? ''}</Text>
        </View>
      ))}
      {view.journal.choices.length ? (
        <View className="gap-1">
          <Text className="font-sans-semibold text-panel text-fg-muted">{ko.endingChoices}</Text>
          {view.journal.choices.map((c, i) => (
            <Text key={`${c.name}${i}`} className="font-sans text-panel text-fg-default">
              {c.chapter} · {c.kind === 'fork' ? ko.fork : ko.cost} · {c.name}
            </Text>
          ))}
        </View>
      ) : null}
      <Pressable accessibilityRole="button" onPress={onNew} className="mt-auto items-center rounded-md bg-gold-fg py-3">
        <Text className="font-sans-semibold text-body text-fg-on-emphasis">{ko.newGame}</Text>
      </Pressable>
    </View>
  );
}
