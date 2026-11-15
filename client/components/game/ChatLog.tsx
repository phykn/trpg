import { useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { speakerHue } from '@/components/game/speaker';
import { pressed } from '@/components/ui/Button';
import type { Entry } from '@/logic/useGame';

// The DM narrates scenes and speaks to the player in one voice, so its lines read like any other narration.
const TEXT_KINDS = ['text', 'ending', 'omen', 'event', 'guide'];

function Typing() {
  const [n, setN] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setN((k) => (k % 3) + 1), 400);
    return () => clearInterval(id);
  }, []);
  return (
    <View accessibilityLabel="…" className="h-6 flex-row items-center gap-1.5">
      {[1, 2, 3].map((i) => (
        <View key={i} className={`h-2 w-2 rounded-full bg-fg-subtle ${i === n ? 'opacity-100' : 'opacity-30'}`} />
      ))}
    </View>
  );
}

function Item({ entry, people, typing, onNote }: {
  entry: Entry; people: string[]; typing: boolean; onNote: (lines: number[]) => void;
}) {
  if (typing && 'who' in entry && entry.who) {
    const hue = speakerHue(people, entry.who);
    return (
      <View className={`gap-0.5 border-l-2 pl-3 ${hue.border}`}>
        <Text className={`font-sans-semibold text-chip ${hue.text}`}>{entry.who}</Text>
        <Typing />
      </View>
    );
  }
  if (typing) return <Typing />;
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

export function ChatLog({ log, people, waiting, outgoing, onNote }: {
  log: Entry[]; people: string[]; waiting: 'sending' | 'streaming' | null; outgoing: string | null;
  onNote: (lines: number[]) => void;
}) {
  const ref = useRef<ScrollView>(null);
  // Texts stream turn by turn and slot by slot, so the first empty one is the one being written.
  const typing = waiting === 'streaming' ? log.find((e) => TEXT_KINDS.includes(e.kind) && 'who' in e && !e.text)?.key : undefined;
  return (
    <ScrollView ref={ref} className="min-h-0 flex-1" contentContainerClassName="gap-3 px-4 py-4"
      onContentSizeChange={() => ref.current?.scrollToEnd({ animated: false })}>
      {log.map((entry) => <Item key={entry.key} entry={entry} people={people} typing={entry.key === typing} onNote={onNote} />)}
      {outgoing ? <Item entry={{ key: 'outgoing', kind: 'said', text: outgoing }} people={people} typing={false} onNote={onNote} /> : null}
      {waiting === 'sending' ? <Typing /> : null}
    </ScrollView>
  );
}
