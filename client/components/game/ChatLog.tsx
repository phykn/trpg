import { useRef } from 'react';
import { ScrollView, Text, View } from 'react-native';

import type { Entry } from '@/logic/useGame';

function Item({ entry }: { entry: Entry }) {
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
      return <Text className="font-sans text-chip italic text-gold-fg">{entry.text}</Text>;
    case 'omen':
    case 'event':
      return entry.text ? (
        <Text className="border-l-2 border-danger-fg pl-3 font-serif-body text-body text-fg-default">{entry.text}</Text>
      ) : null;
    default:
      if (entry.who) {
        return (
          <View className="gap-0.5">
            <Text className="font-sans-semibold text-chip text-fg-muted">{entry.who}</Text>
            <Text className="font-sans text-body text-fg-default">{entry.text}</Text>
          </View>
        );
      }
      return entry.text ? <Text className="font-serif-body text-body text-fg-default">{entry.text}</Text> : null;
  }
}

export function ChatLog({ log }: { log: Entry[] }) {
  const ref = useRef<ScrollView>(null);
  return (
    <ScrollView ref={ref} className="min-h-0 flex-1" contentContainerClassName="gap-3 px-4 py-4"
      onContentSizeChange={() => ref.current?.scrollToEnd({ animated: false })}>
      {log.map((entry) => <Item key={entry.key} entry={entry} />)}
    </ScrollView>
  );
}
