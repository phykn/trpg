import { Animated, Text, View } from 'react-native';

import { colors, shadow, spacing } from '@/design/tokens';
import { useEntryAnimation } from '@/hooks/useEntryAnimation';
import type { LogEntry } from '@/types/ui';

import { RollResult } from './RollResult';

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
  }
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
      {paragraphs.map((p, i) => (
        <Text
          key={i}
          className="font-serif text-narration text-fg-default"
          style={{ marginTop: i === 0 ? 0 : spacing[3] }}
        >
          {p}
        </Text>
      ))}
    </View>
  );
}

function PlayerMessage({ text }: { text: string }) {
  return (
    <View
      style={{
        borderRightWidth: 2,
        borderRightColor: colors.fg.muted,
        paddingRight: spacing[3],
      }}
    >
      <Text className="font-sans-medium text-lead text-fg-default text-right">
        {text}
      </Text>
    </View>
  );
}

function ActDivider({ text }: { text: string }) {
  const { scale, opacity } = useEntryAnimation();
  return (
    <Animated.View style={{ transform: [{ scale }], opacity }}>
      <View
        className="bg-canvas-subtle border border-border-default rounded-md px-3 py-2.5 flex-row items-start gap-2"
        style={{ borderLeftWidth: 2, borderLeftColor: colors.accent.fg, ...shadow.paper }}
      >
        <Text
          className="font-sans-bold text-caption text-accent-fg"
          style={{ lineHeight: 20 }}
        >
          ◆
        </Text>
        <Text className="font-sans-medium text-body text-fg-default flex-1">
          {text}
        </Text>
      </View>
    </Animated.View>
  );
}
