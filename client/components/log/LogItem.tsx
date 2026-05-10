import { Animated, Text, View } from 'react-native';

import { Glyph, Surface, useEntryAnimation } from '@/components/ui';
import { colors, spacing } from '@/design/tokens';

import { RollResult } from './RollResult';
import type { LogEntry } from '@/logic/log/types';

export function LogItem({ entry }: { entry: LogEntry }) {
  switch (entry.kind) {
    case 'gm':
      return <GMNarration text={entry.text} />;
    case 'player':
      return <PlayerMessage text={entry.text} />;
    case 'act':
      return <ActDivider text={entry.text} />;
    case 'roll':
      return <RollResult entry={entry} />;
    default:
      // Server may add a new log kind ahead of a client deploy — render nothing
      // rather than letting FlatList trip on undefined.
      return null;
  }
}

type Segment = { text: string; kind: 'plain' | 'mark' | 'speech' };

function splitDialogue(text: string): Segment[] {
  const re = /「([^」]*)」/g;
  const parts: Segment[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ text: text.slice(last, m.index), kind: 'plain' });
    parts.push({ text: '「', kind: 'mark' });
    parts.push({ text: m[1], kind: 'speech' });
    parts.push({ text: '」', kind: 'mark' });
    last = re.lastIndex;
  }
  if (last < text.length) parts.push({ text: text.slice(last), kind: 'plain' });
  return parts;
}

function NarrationParts({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((s, i) =>
        s.kind === 'mark' ? (
          <Text key={i} className="text-accent-fg">{s.text}</Text>
        ) : s.kind === 'speech' ? (
          <Text key={i} className="font-sans-medium">{s.text}</Text>
        ) : (
          s.text
        ),
      )}
    </>
  );
}

function GMNarration({ text }: { text: string }) {
  const paragraphs = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.accent.fg,
        paddingLeft: spacing[3],
      }}
    >
      {paragraphs.map((p, i) => {
        return (
          <Text
            key={i}
            className="font-serif text-narration text-fg-default"
            style={{ marginTop: i === 0 ? 0 : spacing[3] }}
          >
            <NarrationParts segments={splitDialogue(p)} />
          </Text>
        );
      })}
    </View>
  );
}

function PlayerMessage({ text }: { text: string }) {
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.exp.fg,
        paddingLeft: spacing[3],
      }}
    >
      <Text className="font-serif text-lead text-accent-fg">
        {text}
      </Text>
    </View>
  );
}

function ActDivider({ text }: { text: string }) {
  const { scale, opacity } = useEntryAnimation();
  return (
    <Animated.View style={{ transform: [{ scale }], opacity }}>
      <Surface
        stripeColor={colors.accent.fg}
        className="px-3 py-2.5 flex-row items-start gap-2"
      >
        <Glyph kind="filled" tone="accent" size={11} style={{ lineHeight: 20 }} />
        <Text className="font-sans-medium text-body text-fg-default flex-1">
          {text}
        </Text>
      </Surface>
    </Animated.View>
  );
}
