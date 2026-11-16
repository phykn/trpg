import { Pressable, ScrollView, Text, View } from 'react-native';

import { Button, pressed } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import { GROUPS } from '@/logic/notebook';
import type { GameView, Group } from '@/services/types';
import { Marks } from './Marks';

const Unread = () => <View className="h-1.5 w-1.5 rounded-full bg-gold-fg" />;

export function NotebookSheet({ view, group, onGroup, onLine, onConclude, onClose }: {
  view: GameView; group: Group; onGroup: (group: Group) => void; onLine: (id: number) => void; onConclude?: () => void;
  onClose: () => void;
}) {
  return (
    <Sheet full title={ko.notebook} icon="book" onClose={onClose}>
      <View accessibilityRole="tablist" className="flex-row gap-1">
        {GROUPS.map((g) => (
          <Pressable key={g} accessibilityRole="tab" accessibilityState={{ selected: g === group }} onPress={() => onGroup(g)}
            style={pressed}
            className={`h-9 min-w-0 flex-1 flex-row items-center justify-center gap-1 rounded-full ${g === group ? 'bg-fg-default' : 'bg-canvas-subtle'}`}>
            <Text numberOfLines={1} className={`font-sans-semibold text-chip ${g === group ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>
              {ko.groups[g]}
            </Text>
            {view.notebook[g].some((l) => l.new) ? <Unread /> : null}
          </Pressable>
        ))}
      </View>
      <ScrollView className="min-h-0 flex-1" contentContainerClassName="gap-2">
        {view.notebook[group].map((line) => {
          const place = group === 'places';
          // A line opens only when its sheet holds more than the card: a place's whole look, gathered lines, acts.
          const opens = (place && line.intro) || line.about.length || line.acts.length;
          const body = (
            <>
              <View className="flex-row items-center gap-2">
                <Text className={`min-w-0 flex-1 font-sans text-body text-fg-default ${line.struck ? 'line-through opacity-60' : ''}`}>
                  {line.text}
                </Text>
                {line.new ? <Unread /> : null}
              </View>
              {line.intro ? <Text numberOfLines={place ? 1 : undefined} className="font-sans text-chip text-fg-muted">{line.intro}</Text> : null}
              <Marks marks={line.marks} />
            </>
          );
          const card = 'gap-1.5 rounded-xl border border-border-default bg-canvas-default px-3 py-2.5';
          return opens ? (
            <Pressable key={line.id} accessibilityRole="button" onPress={() => onLine(line.id)} style={pressed} className={card}>
              {body}
            </Pressable>
          ) : <View key={line.id} className={card}>{body}</View>;
        })}
      </ScrollView>
      {onConclude ? <Button tone="secondary" icon="flag" label={ko.conclude} onPress={onConclude} /> : null}
    </Sheet>
  );
}
