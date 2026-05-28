import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { Discoveries, DiscoveryEntry } from '@/logic/discoveries';

type Props = {
  discoveries: Discoveries;
};

export function DiscoveriesPanel({ discoveries }: Props) {
  const hasMemories = discoveries.memories.length > 0;
  const hasClues = discoveries.clues.length > 0;
  if (!hasMemories && !hasClues) return null;

  return (
    <View className="mx-5 gap-2 rounded-sm border border-border-default bg-canvas-inset px-3 py-2">
      {hasClues ? (
        <DiscoveryGroup title={ko.discoveries.clues} entries={discoveries.clues} />
      ) : null}
      {hasMemories ? (
        <DiscoveryGroup title={ko.discoveries.memories} entries={discoveries.memories} />
      ) : null}
    </View>
  );
}

function DiscoveryGroup({ title, entries }: { title: string; entries: DiscoveryEntry[] }) {
  return (
    <View className="gap-1">
      <Text className="font-sans-semibold text-caption text-fg-muted">{title}</Text>
      {entries.map((entry) => (
        <View key={entry.id} className="gap-0.5">
          <Text className="font-sans-semibold text-caption text-fg-default" numberOfLines={1}>
            {entry.title}
          </Text>
          {entry.summary !== entry.title ? (
            <Text className="font-sans text-caption text-fg-muted" numberOfLines={2}>
              {entry.summary}
            </Text>
          ) : null}
        </View>
      ))}
    </View>
  );
}
