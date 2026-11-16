import { type ReactNode, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { text } from '@/design/ui';
import { splitTopics } from '@/logic/topics';
import type { Entry } from '@/logic/useGame';
import { findHue } from './speaker';

function Typing() {
  const [lit, setLit] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setLit((n) => (n % 3) + 1), 400);
    return () => clearInterval(id);
  }, []);
  return (
    <View accessibilityLabel="…" className="h-6 flex-row items-center gap-1.5">
      {[1, 2, 3].map((i) => <View key={i} className={`h-2 w-2 rounded-full bg-fg-subtle ${i === lit ? 'opacity-100' : 'opacity-30'}`} />)}
    </View>
  );
}

function Speaker({ who, met, children }: { who: string; met: string[]; children: ReactNode }) {
  const hue = findHue(met, who);
  return (
    <View className={`gap-0.5 border-l-2 pl-3 ${hue.border}`}>
      <Text className={`font-sans-semibold text-chip ${hue.text}`}>{who}</Text>
      {children}
    </View>
  );
}

function Line({ entry, met, typing, onNote }: {
  entry: Entry; met: string[]; typing: boolean; onNote: (lines: number[]) => void;
}) {
  if (entry.kind === 'said') {
    return (
      <View className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-gold-muted px-3 py-2">
        <Text className={text()}>{entry.text}</Text>
      </View>
    );
  }
  if (entry.kind === 'move') return <Text className="py-1 text-center font-mono-medium text-chip text-fg-subtle">{entry.text}</Text>;
  if (entry.kind === 'roll') {
    return <Text className={`font-mono-medium text-panel ${entry.won ? 'text-health-fg' : 'text-danger-fg'}`}>{entry.text}</Text>;
  }
  if (entry.kind === 'note') {
    return (
      <Pressable accessibilityRole="button" onPress={() => onNote(entry.lines)} style={pressed} className="self-start">
        <Text className={text({ kind: 'notice' })}>{entry.text}</Text>
      </Pressable>
    );
  }
  // Text slots: a person's answer under their name, happenings marked in red, every other narration in one voice.
  if (entry.who) {
    return (
      <Speaker who={entry.who} met={met}>
        {typing ? <Typing /> : (
          <Text className={text()}>
            {splitTopics(entry.text, entry.topics).map((part, i) => (
              part.topic ? <Text key={i} className={text({ kind: 'topic' })}>{part.text}</Text> : part.text
            ))}
          </Text>
        )}
      </Speaker>
    );
  }
  if (typing) return <Typing />;
  if (!entry.text) return null;
  const happening = entry.kind === 'omen' || entry.kind === 'event';
  return (
    <Text className={text({ kind: 'scene' }, happening && 'border-l-2 border-danger-fg pl-3')}>{entry.text}</Text>
  );
}

export function ChatLog({ log, met, waiting, outgoing, onNote }: {
  log: Entry[]; met: string[]; waiting: 'sending' | 'streaming' | null; outgoing: Entry | null;
  onNote: (lines: number[]) => void;
}) {
  const ref = useRef<ScrollView>(null);
  // While the reader is at the newest line, it stays in view when the box shrinks (the keyboard comes up) or grows.
  const atBottom = useRef(true);
  // Texts stream turn by turn and slot by slot, so the first empty one is the one being written.
  const writing = waiting === 'streaming' ? log.find((e) => 'slot' in e && !e.text) : undefined;
  return (
    <ScrollView ref={ref} className="min-h-0 flex-1" contentContainerClassName="gap-3 px-4 py-4"
      onContentSizeChange={() => ref.current?.scrollToEnd({ animated: false })}
      onLayout={() => atBottom.current && ref.current?.scrollToEnd({ animated: false })} scrollEventThrottle={100}
      onScroll={({ nativeEvent: { contentOffset, contentSize, layoutMeasurement } }) => {
        atBottom.current = contentOffset.y + layoutMeasurement.height >= contentSize.height - 24;
      }}>
      {log.map((e) => <Line key={e.key} entry={e} met={met} typing={e === writing} onNote={onNote} />)}
      {outgoing ? <Line entry={outgoing} met={met} typing={false} onNote={onNote} /> : null}
      {waiting === 'sending' ? <Typing /> : null}
    </ScrollView>
  );
}
