import { Pressable, Text, View } from 'react-native';

import type { ListEntry } from './PagedList';

export function MenuGrid({ entries, onSelect, disabled }: { entries: ListEntry[]; onSelect: (id: string) => void; disabled?: boolean }) {
  return (
    <View className="flex-1 min-h-0 gap-3">
      {Array.from({ length: Math.ceil(entries.length / 2) }, (_, row) => (
        <View key={row} className="flex-1 flex-row gap-3" style={{ maxHeight: 112 }}>
          {entries.slice(row * 2, row * 2 + 2).map((entry) => (
            <Pressable key={entry.id} accessibilityRole="button" accessibilityLabel={entry.label} accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={() => onSelect(entry.id)} className={`flex-1 min-h-11 justify-center gap-2 rounded-lg border border-border-default bg-canvas-subtle p-3 active:bg-canvas-floating ${disabled ? 'opacity-50' : ''}`}>
              <Text className="font-sans-semibold text-body text-fg-default">{entry.label}</Text>
              {entry.meta ? <Text className="font-sans text-caption text-gold-fg">{entry.meta}</Text> : null}
            </Pressable>
          ))}
          {entries.length === row * 2 + 1 ? <View className="flex-1" /> : null}
        </View>
      ))}
    </View>
  );
}
