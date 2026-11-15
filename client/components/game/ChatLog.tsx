import { useRef } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { speakerHue } from '@/components/game/speaker';
import { pressed } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { Entry } from '@/logic/useGame';

function Item({ entry, people, onNote }: { entry: Entry; people: string[]; onNote: (lines: number[]) => void }) {
  switch (entry.kind) {
    case 'said':
      return (
        <View className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-gold-muted px-3 py-2">
          <Text className="font-sans text-body text-fg-default">{entry.text}</Text>
        </View>
      );
    case 'move':
      return <Text className="py-1 text-center font-mono-medium text-chip text-fg-subtle">{entry.text}</Text>;
    case 'roll':
      return (
        <Text className={`font-mono-medium text-panel ${entry.won ? 'text-health-fg' : 'text-danger-fg'}`}>{entry.text}</Text>
      );
    case 'note':
      return (
        <Pressable accessibilityRole="button" onPress={() => onNote(entry.lines)} style={pressed} className="self-start">
          <Text className="font-sans text-chip italic text-gold-fg">{entry.text}</Text>
        </Pressable>
      );
    case 'guide':
      return entry.text ? (
        <View className="gap-0.5 rounded-lg bg-canvas-subtle px-3 py-2">
          <Text className="font-mono-medium text-chip text-fg-subtle">{ko.dm}</Text>
          <Text className="font-sans text-panel text-fg-default">{entry.text}</Text>
        </View>
      ) : null;
    case 'omen':
    case 'event':
      return entry.text ? (
        <Text className="border-l-2 border-danger-fg pl-3 font-serif-body text-body text-fg-default">{entry.text}</Text>
      ) : null;
    default:
      if (entry.who) {
        const hue = speakerHue(people, entry.who);
        return (
          <View className={`gap-0.5 border-l-2 pl-3 ${hue.border}`}>
            <Text className={`font-sans-semibold text-chip ${hue.text}`}>{entry.who}</Text>
            <Text className="font-sans text-body text-fg-default">{entry.text}</Text>
          </View>
        );
      }
      return entry.text ? <Text className="font-serif-body text-body text-fg-default">{entry.text}</Text> : null;
  }
}

export function ChatLog({ log, people, onNote }: { log: Entry[]; people: string[]; onNote: (lines: number[]) => void }) {
  const ref = useRef<ScrollView>(null);
  return (
    <ScrollView ref={ref} className="min-h-0 flex-1" contentContainerClassName="gap-3 px-4 py-4"
      onContentSizeChange={() => ref.current?.scrollToEnd({ animated: false })}>
      {log.map((entry) => <Item key={entry.key} entry={entry} people={people} onNote={onNote} />)}
    </ScrollView>
  );
}
