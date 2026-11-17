import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { text } from '@/design/ui';
import { splitTopics } from '@/logic/topics';
import type { Entry } from '@/logic/useGame';
import { RollLine } from '@/components/dice/RollParts';
import { ko } from '@/locale/ko';
import { findHue } from './speaker';
import type { Topic } from './TopicCard';

export function Typing() {
  const [lit, setLit] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setLit((n) => (n % 3) + 1), 400);
    return () => clearInterval(id);
  }, []);
  return (
    <View role="status" accessibilityLabel={ko.waiting} className="h-6 flex-row items-center gap-1.5">
      {[1, 2, 3].map((i) => <View key={i} className={`h-2 w-2 rounded-full bg-fg-subtle ${i === lit ? 'opacity-100' : 'opacity-30'}`} />)}
    </View>
  );
}

export function Speaker({ who, met, children }: { who: string; met: string[]; children: ReactNode }) {
  const hue = findHue(met, who);
  return (
    <View className={`gap-0.5 border-l-2 pl-3 ${hue.border}`}>
      <Text className={text({ kind: 'head' }, hue.text)}>{who}</Text>
      {children}
    </View>
  );
}

// The unheard topic names a text names are underlined in blue (docs/game/04-talk.md 5); a tap shows what one is.
export function Spoken({ text: words, topics, className, onTopic }: {
  text: string; topics?: string[]; className: string; onTopic?: (name: string) => void;
}) {
  return (
    <Text className={className}>
      {splitTopics(words, topics).map((part, i) => (
        part.topic ? (
          <Text key={i} accessibilityRole={onTopic ? 'button' : undefined} onPress={onTopic && (() => onTopic(part.text))}
            className={text({ kind: 'topic' })}>{part.text}</Text>
        ) : part.text
      ))}
    </Text>
  );
}

function Line({ entry, met, typing, onNote, onTopic }: {
  entry: Entry; met: string[]; typing: boolean; onNote: (lines: number[]) => void; onTopic: (topic: Topic) => void;
}) {
  if (entry.kind === 'said') {
    return (
      <View className="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-gold-muted px-3 py-2">
        <Text className={text()}>{entry.text}</Text>
      </View>
    );
  }
  if (entry.kind === 'move') return <Text className="py-1 text-center font-mono-medium text-chip text-fg-subtle">{entry.text}</Text>;
  if (entry.kind === 'roll') return <RollLine result={entry} />;
  if (entry.kind === 'note') {
    return (
      <Pressable accessibilityRole="button" onPress={() => onNote(entry.lines)} style={pressed} className="self-start">
        <Text className={text({ kind: 'notice' })}>{entry.text}</Text>
      </Pressable>
    );
  }
  if (!entry.text && !typing) return null;
  if (entry.who) {
    return (
      <Speaker who={entry.who} met={met}>
        {typing ? <Typing /> : <Spoken text={entry.text} topics={entry.topics} className={text()}
          onTopic={(name) => onTopic({ name, who: entry.who })} />}
      </Speaker>
    );
  }
  if (typing) return <Typing />;
  const happening = entry.kind === 'omen' || entry.kind === 'event';
  return (
    <Spoken text={entry.text} topics={entry.topics} className={text({ kind: 'scene' }, happening && 'border-l-2 border-danger-fg pl-3')}
      onTopic={(name) => onTopic({ name, who: null })} />
  );
}

export function ChatLog({ log, met, waiting, outgoing, onNote, onTopic }: {
  log: Entry[]; met: string[]; waiting: 'sending' | 'streaming' | null; outgoing: Entry | null;
  onNote: (lines: number[]) => void; onTopic: (topic: Topic) => void;
}) {
  const ref = useRef<ScrollView>(null);
  // While the reader is at the newest line, it stays in view when the box shrinks (the keyboard comes up) or grows.
  const atBottom = useRef(true);
  const scrollTop = useRef(0);
  const outgoingKey = outgoing?.key;
  useLayoutEffect(() => {
    if (!outgoingKey) return;
    atBottom.current = true;
    ref.current?.scrollToEnd({ animated: false });
  }, [outgoingKey]);
  // Texts stream turn by turn and slot by slot, so the first empty one is the one being written.
  const writing = waiting === 'streaming' ? log.findIndex((e) => 'slot' in e && !e.text) : -1;
  const lines = writing === -1 ? log : log.slice(0, writing + 1);
  return (
    <ScrollView ref={ref} className="min-h-0 flex-1" contentContainerClassName="gap-3 px-4 py-4"
      onContentSizeChange={() => atBottom.current && ref.current?.scrollToEnd({ animated: false })}
      onLayout={() => atBottom.current && ref.current?.scrollToEnd({ animated: false })} scrollEventThrottle={16}
      onScroll={({ nativeEvent: { contentOffset, contentSize, layoutMeasurement } }) => {
        const y = contentOffset.y;
        if (y + layoutMeasurement.height >= contentSize.height - 24) atBottom.current = true;
        else if (y < scrollTop.current) atBottom.current = false;
        scrollTop.current = y;
      }}>
      {lines.map((e, index) => <Line key={e.key} entry={e} met={met} typing={index === writing} onNote={onNote} onTopic={onTopic} />)}
      {outgoing ? <Line entry={outgoing} met={met} typing={false} onNote={onNote} onTopic={onTopic} /> : null}
      {waiting === 'sending' ? <Typing /> : null}
    </ScrollView>
  );
}
