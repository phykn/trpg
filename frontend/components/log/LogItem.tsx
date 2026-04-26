import { Text, View } from 'react-native';

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
  return <Text className="font-serif text-lead text-fg-default">{text}</Text>;
}

function PlayerMessage({ text }: { text: string }) {
  return (
    <View
      className="self-end py-2.5 px-3.5 bg-accent-muted rounded-md"
      style={{ maxWidth: '82%', borderBottomRightRadius: 6 }}
    >
      <Text className="font-mono-medium text-title text-accent-fg">{text}</Text>
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
