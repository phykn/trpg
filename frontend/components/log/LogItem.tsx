import { Text, View } from 'react-native';

import { colors, spacing } from '@/design/tokens';
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
  return (
    <View
      style={{
        borderLeftWidth: 2,
        borderLeftColor: colors.accent.fg,
        paddingLeft: spacing[3],
      }}
    >
      <Text className="font-serif text-lead text-fg-default">{text}</Text>
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
      <Text className="font-mono-medium text-title text-fg-default text-right">
        {text}
      </Text>
    </View>
  );
}

function ActDivider({ text }: { text: string }) {
  return (
    <Text className="font-mono text-body text-fg-subtle italic text-center px-5">
      — {text} —
    </Text>
  );
}
